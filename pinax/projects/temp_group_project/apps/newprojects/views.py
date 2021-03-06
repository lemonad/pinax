from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils.datastructures import SortedDict
from django.utils.translation import ugettext_lazy as _

from django.conf import settings

if "notification" in settings.INSTALLED_APPS:
    from notification import models as notification
else:
    notification = None

from newprojects.models import Project
from newprojects.forms import ProjectForm, ProjectUpdateForm

TOPIC_COUNT_SQL = """
SELECT COUNT(*)
FROM topics_topic
WHERE
    topics_topic.object_id = newprojects_project.id AND
    topics_topic.content_type_id = %s
"""
MEMBER_COUNT_SQL = """
SELECT COUNT(*)
FROM newprojects_project_members
WHERE newprojects_project_members.project_id = newprojects_project.id
"""

@login_required
def create(request, form_class=ProjectForm, template_name="newprojects/create.html"):
    project_form = form_class(request.POST or None)
    
    if project_form.is_valid():
        project = project_form.save(commit=False)
        project.creator = request.user
        project.save()
        project.members.add(request.user)
        project.save()
        if notification:
            # @@@ might be worth having a shortcut for sending to all users
            notification.send(User.objects.all(), "projects_new_project",
                {"project": project}, queue=True)
        return HttpResponseRedirect(project.get_absolute_url())
    
    return render_to_response(template_name, {
        "project_form": project_form,
    }, context_instance=RequestContext(request))


def projects(request, template_name="newprojects/projects.html"):
    
    ctype = ContentType.objects.get_for_model(Project)
    
    projects = Project.objects.all()
    search_terms = request.GET.get('search', '')
    if search_terms:
        projects = (projects.filter(name__icontains=search_terms) |
            projects.filter(description__icontains=search_terms))
    
    content_type = ContentType.objects.get_for_model(Project)
    
    projects = projects.extra(select=SortedDict([
        ('member_count', MEMBER_COUNT_SQL),
        ('topic_count', TOPIC_COUNT_SQL),
    ]), select_params=(content_type.id,))
    
    return render_to_response(template_name, {
        'projects': projects,
        'search_terms': search_terms,
    }, context_instance=RequestContext(request))


def delete(request, group_slug=None, redirect_url=None):
    project = get_object_or_404(Project, slug=group_slug)
    if not redirect_url:
        redirect_url = reverse('project_list')
    
    # @@@ eventually, we'll remove restriction that project.creator can't leave project but we'll still require project.members.all().count() == 1
    if (request.user.is_authenticated() and request.method == "POST" and
            request.user == project.creator and project.members.all().count() == 1):
        project.delete()
        request.user.message_set.create(message=_("Project %s deleted.") % (
            project,))
        # no notification required as the deleter must be the only member
    
    return HttpResponseRedirect(redirect_url)


@login_required
def your_projects(request, template_name="newprojects/your_projects.html"):
    return render_to_response(template_name, {
        "projects": Project.objects.filter(members=request.user).order_by("name"),
    }, context_instance=RequestContext(request))


def project(request, group_slug=None, form_class=ProjectUpdateForm,
        template_name="newprojects/project.html"):
    project = get_object_or_404(Project, slug=group_slug)
    
    project_form = form_class(request.POST or None, instance=project)
    
    action = request.POST.get('action')
    if action == 'update' and project_form.is_valid():
        project = project_form.save()
    elif action == 'join':
        project.members.add(request.user)
        request.user.message_set.create(
            message=_("You have joined the project %s") % (project.name,))
        if notification:
            notification.send([project.creator], "projects_created_new_member", {"user": request.user, "project": project})
            notification.send(project.members.all(), "projects_new_member", {"user": request.user, "project": project})
    elif action == 'leave':
        project.members.remove(request.user)
        request.user.message_set.create(message="You have left the project %s" % project.name)
        if notification:
            pass # @@@ no notification on departure yet
    
    if request.user.is_authenticated():
        is_member = False
    else:
        is_member = project.user_is_member(request.user)
    
    # TODO: Shouldn't have to do this in the view. Should write new "groupurl" templatetag :(
    new_topic_url = reverse('topic_list', kwargs=project.get_url_kwargs())
    
    return render_to_response(template_name, {
        "project_form": project_form,
        "project": project,
        "is_member": is_member,
        "new_topic_url": new_topic_url,
    }, context_instance=RequestContext(request))
