from django.conf.urls import url, include
from ct_projects import views

__author__ = 'dipap'

urlpatterns = [
    # projects lists
    url(r'^$', views.list_projects, name='all-projects'),
    url(r'^followed-projects/$', views.followed_projects, name='followed-projects'),

    # ideas
    url(r'^(?P<pk>[\w-]+)/post-idea/$', views.post_idea, name='post-idea'),
    url(r'^(?P<project_pk>[\w-]+)/ideas/(?P<pk>\d+)$', views.idea_details, name='idea-details'),

    # project details
    url(r'^(?P<pk>[\w-]+)/$', views.project_details, name='project-details'),

    # following projects
    url(r'^(?P<pk>[\w-]+)/follow/$', views.follow_project, name='follow-project'),
    url(r'^(?P<pk>[\w-]+)/unfollow/$', views.unfollow_project, name='unfollow-project'),

    # comments
    url(r'^comments/posted/$', views.comment_posted),
    url(r'^comments/', include('django_comments.urls')),
]
