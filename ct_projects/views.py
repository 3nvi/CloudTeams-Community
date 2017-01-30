from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.urlresolvers import reverse
from django.db.models import Q, Count
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import DetailView
from django_comments.forms import CommentForm
from django_comments.models import Comment

from ct_projects.forms import IdeaForm, IdeaRatingForm
from ct_projects.models import *


def how_it_works(request):
    return render(request, 'ct_projects/how-it-works.html', {
        'light_menu': True,
    })


def who_are_you(request, next_page):
    if next_page.lower() == 'register':
        customer_next = '/activitytracker/account/register/'
        developer_next = '/developer/account/register'
    else:
        customer_next = '/activitytracker/login/'
        developer_next = 'https://teams.cloudteams.eu/pub/'

    return render(request, 'ct_projects/who-are-you.html', {
        'light_menu': True,
        'login_button': True,

        'customer_next': customer_next,
        'developer_next': developer_next,
    })


def developer_registration(request):
    return render(request, 'ct_projects/register-developer.html', {
        'light_menu': True,
        'login_button': True,
    })


def list_projects(request):
    """
    A list of all projects in cloud teams
    """
    q = request.GET.get('q', '')
    qs = Project.objects.filter(Q(title__icontains=q) | Q(description__icontains=q) |
                                Q(category__icontains=q))

    # ordering
    order = request.GET.get('order', 'trending')
    if order == 'trending':
        qs = qs.order_by('-trend_factor')
    elif order == 'most-popular':
        qs = qs.annotate(num_followers=Count('followed')).order_by('-num_followers', '-created')
    else:
        order = 'latest'
        qs = qs.order_by('-created')

    pages = Paginator(qs, 12)

    context = {
        'n_of_projects': Project.objects.all().count(),
        'page_obj': pages.page(int(request.GET.get('page', '1'))),
        'q': q,
        'order': order,
        'light_menu': not request.user.is_authenticated(),
    }

    return render(request, 'ct_projects/project/all.html', context)


@login_required
def followed_projects(request):
    """
    A list of projects in cloud teams that I follow
    """
    q = request.GET.get('q', '')

    n_of_followed = ProjectFollowing.objects.filter(user=request.user).count()
    projects = [f.project for f in ProjectFollowing.objects.filter(user=request.user)]

    context = {
        'projects': projects,
        'n_of_followed': n_of_followed,
    }

    return render(request, 'ct_projects/project/dashboard.html', context)


@login_required
def dashboard_campaigns(request):
    """
    A list of projects in cloud teams that I follow
    """
    # find participated campaigns
    campaigns_participated = request.user.get_participated_campaigns()

    # find invited campaigns
    campaigns_invited = []
    for n in Notification.objects.filter(user=request.user).exclude(Q(document=None) & Q(poll=None)):
        c = n.campaign()
        if c not in campaigns_participated and not c.has_expired():
            campaigns_invited.append(c)

    # unique
    campaigns_invited = list(set(campaigns_invited))

    # find running campaigns where user has not already participated
    campaigns_running = []
    for c in Campaign.objects.all():
        if not c.has_expired() and c not in campaigns_participated:
            campaigns_running.append(c)

    context = {
        'campaigns_invited': campaigns_invited,
        'campaigns_running': campaigns_running,
        'campaigns_participated': campaigns_participated,
        'tab': request.GET.get('tab', 'invited'),
    }

    return render(request, 'ct_projects/campaign/dashboard.html', context)


@login_required
def follow_project(request, pk):
    # only posts allowed to this method
    if request.method == 'POST':
        # get project
        project = Project.objects.get(pk=pk)
        if not project:
            return HttpResponse('Project #%d does not exist' % pk, status=404)

        # check if already followed
        if ProjectFollowing.objects.filter(project=project, user=request.user):
            return HttpResponse('You are already following project #%s' % pk, status=403)

        # follow & return OK
        ProjectFollowing.objects.create(project=project, user=request.user)
        return redirect(reverse('project-details', args=(pk, )))
    else:
        return HttpResponse('Only POST allowed', status=400)


def get_project_ideas(request, pk):
    try:
        project = Project.objects.get(pk=pk)
    except Project.DoesNotExist:
        return HttpResponse('Project with id #%d was not found' % pk, status=404)

    return render(request, 'ct_projects/idea/list.html', {
        'project': project,
        'ideas': project.ideas.all(),
    })


def contact_project_team(request, pk):
    try:
        project = Project.objects.get(pk=pk)
    except Project.DoesNotExist:
        return HttpResponse('Project with id #%d was not found' % pk, status=404)

    if ContactRequest.objects.filter(user_id=request.user.pk, project_id=pk):
        return HttpResponse('Contact request already sent', status=400)

    provided_info = request.POST.get('provided_info', '')
    message = request.POST.get('message', '')

    if not provided_info:
        return HttpResponse('`provided_info` is required', status=400)

    cr = ContactRequest.objects.create(user=request.user, project=project,
                                       provided_info=provided_info,
                                       message=message)

    return HttpResponse('Contact request sent to project team (Request ID: #%d)' % cr.pk)


@login_required
def unfollow_project(request, pk):
    # only posts allowed to this method
    if request.method == 'POST':
        # get project
        project = Project.objects.get(pk=pk)
        if not project:
            return HttpResponse('Project #%s does not exist' % pk, status=404)

        # check if actually followed
        pfs = ProjectFollowing.objects.filter(project=project, user=request.user)
        if not pfs:
            return HttpResponse('You are not following project #%s' % pk, status=403)

        # unfollow & return OK
        pfs.delete()
        return redirect(reverse('project-details', args=(pk, )))
    else:
        return HttpResponse('Only POST allowed', status=400)


def project_details(request, pk):
    """
    View the details page of a specific project
    """
    # only gets allowed to this method
    if request.method == 'GET':
        # get project
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            raise Http404()

        if not project:
            return HttpResponse('Project #%s does not exist' % pk, status=404)

        context = {
            'project': project,
            'idea_form': IdeaForm(),
        }

        if request.GET.get('tab', '') == 'ideas':
            context['tab'] = 'ideas'

        # increase project views
        project.increase_views()

        return render(request, 'ct_projects/project/details.html', context)
    else:
        return HttpResponse('Only GET allowed', status=400)


def handler_404(request):
    return render(request, '404.html', {
        'light_menu': True,
        'register': False,
    })


@login_required
def post_idea(request, pk):
    """
    Post a new idea on a project
    """
    # get project
    project = Project.objects.get(pk=pk)
    if not project:
        return HttpResponse('Project #%s does not exist' % pk, status=404)

    context = {
        'project': project
    }
    status = 200

    if request.method == 'GET':
        context['form'] = IdeaForm()
    elif request.method == 'POST':
        form = IdeaForm(request.POST)

        if form.is_valid():
            # save the idea
            idea = form.save(commit=False)
            idea.user = request.user
            idea.project = project
            idea.save()

            # redirect to project home page
            return redirect(reverse('project-details', args=(pk, )) + '?tab=ideas')
        else:
            context['form'] = form
            status = 400
    else:
        return HttpResponse('Only GET,POST allowed', status=400)

    return render(request, 'ct_projects/project/post-idea.html', context, status=status)


def comment_posted(request):
    if request.GET['c']:
        comment_id = request.GET['c']
        comment = Comment.objects.get(pk=comment_id)
        idea = Idea.objects.get(id=comment.object_pk)
        if idea:
            return redirect('/projects/%d/?tab=ideas' % idea.project_id)


@login_required
def like_unlike_project(request, pk, action):
    get_object_or_404(Project, pk=pk)

    # try to get like
    try:
        like = ProjectLike.objects.get(project_id=pk, user_id=request.user.pk)

        if action == 'like':
            return HttpResponse('Can not re-like', status=400)
    except ProjectLike.DoesNotExist:

        if action == 'unlike':
            return HttpResponse('Can not unlike', status=400)

    # create or delete like
    if action == 'like':
        ProjectLike.objects.create(project_id=pk, user_id=request.user.pk)
    else:
        like.delete()

    return redirect('/projects/%s/' % pk)


@login_required
def rate_idea(request, project_pk, pk):
    idea = get_object_or_404(Idea, pk=pk)

    if request.method == 'POST':
        if idea.ratings.filter(user=request.user):
            # unlike
            idea.ratings.filter(user=request.user).delete()

            return redirect(reverse('project-details', args=(idea.project.pk,)) + '?tab=ideas')

        # save the rating
        form = IdeaRatingForm(request.POST)
        rating = form.save(commit=False)
        rating.user = request.user
        rating.idea = idea
        rating.save()

        return redirect(reverse('project-details', args=(idea.project.pk, )) + '?tab=ideas')
    else:
        return HttpResponse('Only POST allowed', status=400)


class CampaignDetailView(DetailView):
    model = Campaign
    template_name = 'ct_projects/campaign/details.html'
    context_object_name = 'campaign'

    def get_context_data(self, **kwargs):
        ctx = super(CampaignDetailView, self).get_context_data(**kwargs)
        ctx['idea_form'] = IdeaForm()
        return ctx

campaign_details = CampaignDetailView.as_view()


@login_required
def request_poll_token(request, project_pk, pk):
    poll = get_object_or_404(Poll, pk=pk)
    return redirect(poll.get_poll_token_link(request.user))


class BlogPostDetailView(DetailView):
    model = BlogPost
    template_name = 'ct_projects/blogposts/details.html'
    context_object_name = 'blog'

blog_details = BlogPostDetailView.as_view()


# Rewards views
@login_required
def rewards(request):
    return render(request, 'ct_projects/reward/index.html', {
        'store_rewards': Reward.available_rewards(user=request.user),
        'purchases': RewardPurchase.objects.filter(user=request.user),
        'tab': request.GET.get('tab', 'store')
    })


@login_required
def purchase_reward(request, reward_pk):
    try:
        reward = Reward.objects.get(pk=reward_pk)
    except Reward.DoesNotExist:
        return HttpResponse('Reward was not found', status=404)

    try:
        purchase = reward.purchase(request.user)
    except RewardPurchaseError as e:
        return HttpResponse(str(e), status=400)

    return render(request, 'ct_projects/reward/purchase-table-row.html', {
        'purchase': purchase,
    })


# Project generic views
def terms_and_conditions(request):
    return render(request, 'ct_projects/generic/terms-and-conditions.html')


def privacy_policy(request):
    return render(request, 'ct_projects/generic/privacy-policy.html')
