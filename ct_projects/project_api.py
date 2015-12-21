from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ct_projects.forms import ProjectForm
from ct_projects.models import Project

__author__ = 'dipap'


@csrf_exempt
def project_list(request):
    """
    Methods regarding all project list
    """
    if request.method == 'GET':
        # list existing projects
        return JsonResponse([p.to_json() for p in Project.objects.all()], safe=False)
    elif request.method == 'POST':
        # create a new project
        form = ProjectForm(request.POST)
        if form.is_valid():
            instance = form.save()
            return JsonResponse(instance.to_json(), safe=False)
        else:
            return JsonResponse({'error': form.errors}, status=400)
    else:
        # invalid/unsupported HTTP method
        # do not support PUT/DELETE on project list by default to avoid accidents
        return JsonResponse({'error': 'Method %s not allowed on project list' % request.method}, status=403)


@csrf_exempt
def project(request, pk):
    """
    Methods regarding a specific request
    """
    # find project with ID=pk
    try:
        instance = Project.objects.get(pk=int(pk))
    except ObjectDoesNotExist:
        return JsonResponse({'error': 'Project #%d not found' % int(pk)}, status=404)

    if request.method == 'GET':
        # return project info
        return JsonResponse(instance.to_json(), safe=False)
    elif request.method == 'POST':
        # update project
        form = ProjectForm(request.POST, instance=instance)
        if form.is_valid():
            instance = form.save()
            return JsonResponse(instance.to_json(), safe=False)
        else:
            return JsonResponse({'error': form.errors}, status=400)
    elif request.method == 'DELETE':
        # delete project
        instance.delete()
        return JsonResponse({}, status=204)
    else:
        # invalid/unsupported HTTP method
        return JsonResponse({'error': 'Method %s not allowed on project' % request.method}, status=403)
