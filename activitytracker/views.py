from django.shortcuts import render, redirect
from django.contrib.auth import logout as auth_logout, login as auth_login, authenticate
from activitytracker.models import *
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.template.response import SimpleTemplateResponse
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage
from config import *
import string
import random
import json
import calendar
import operator
import collections
from myfunctions import *
from AuthorizationChecks import *
from config import *
from InstagramClass import Instagram
from TwitterClass import Twitter
from YoutubeClass import Youtube
from RunkeeperClass import Runkeeper
from FitbitClass import Fitbit
from FoursquareClass import Foursquare
from FacebookActivityClass import FacebookActivity
from datetime import datetime

colourDict = {'black': "rgba(1, 1, 1, 0.8)",
              'blue': "#578EBE",
              'greenLight': "#99B433",
              'orange': "#e09100",
              'redDark': "#850521",
              'purple': "#800080"
              }


def terms_and_conditions(request):
    return render(request, 'activitytracker/terms_and_conditions.html', {})


def login(request):

    EMAIL_VERIFICATION_MSG = 'You need to verify your E-mail in order to log in'
    INVALID_USER_MSG = 'No such User exists'
    WRONG_CREDENTIALS_MSG = 'Wrong Combination of Username and Password'

    if request.method != 'POST':
        if request.user.is_authenticated():
            return HttpResponseRedirect(reverse('index'))

        return render(request,
                      'activitytracker/login.html',
                      {'redirect_url': request.GET.get('next',
                                                       '/activitytracker/index'
                                                       )
                       }
                      )

    username = request.POST['username']
    password = request.POST['password']

    if User.objects.filter(username=username).count() == 0:
        return HttpResponseBadRequest(INVALID_USER_MSG)

    user = authenticate(username=username, password=password)

    if user is None:
        return HttpResponseBadRequest(WRONG_CREDENTIALS_MSG)

    if not user.is_active:
        return HttpResponseBadRequest(EMAIL_VERIFICATION_MSG)

    auth_login(request, user)

    return HttpResponse('Ok')


# Flush Session and redirect
def logout(request):

    auth_logout(request)
    return HttpResponseRedirect(reverse('login'))


# Check and Register the User
def register(request):

    USERNAME_EXISTS_MSG = 'UsernameExists'
    EMAIL_EXISTS_MSG = 'EmailExists'
    EMPTY_FIELDS_MSG = 'EmptyFields'
    BIRTHDAY_ERROR_MSG = 'BirthdayError!'
    SUCCESS_MSG = 'Registration Successful! ' \
                  'We have sent you an e-mail with a validation link to follow'

    if request.method != 'POST':
        return render(request, 'activitytracker/register.html')

    username = request.POST['username']
    email = request.POST['email']
    password = request.POST['password']
    firstname = request.POST['firstname']
    lastname = request.POST['lastname']
    gender = request.POST['gender']
    birthday = request.POST['birthday']

    if User.objects.filter(username__iexact=username).exists():
        return HttpResponseBadRequest(USERNAME_EXISTS_MSG)

    if User.objects.filter(email__iexact=email).exists():
        return HttpResponseBadRequest(EMAIL_EXISTS_MSG)

    if '' in (birthday, username, firstname, lastname, email, password):
        return HttpResponseBadRequest(EMPTY_FIELDS_MSG)

    datetime_birthday = datetime.strptime(request.POST['birthday'], "%m/%d/%Y").date()

    if datetime_birthday > datetime.now().date():
        return HttpResponseBadRequest(BIRTHDAY_ERROR_MSG)

    user = User.objects.create_user(username=username,
                                    email=email,
                                    password=password,
                                    first_name=firstname,
                                    last_name=lastname,
                                    gender=gender,
                                    date_of_birth=datetime_birthday
                                    )
    user.is_active = False
    user.save()

    characters = string.ascii_letters + string.digits
    verification_token = ''.join(random.choice(characters) for _ in range(20))
    verification_url = '%s/activitytracker/account/verification/%s' % (SERVER_URL, verification_token)
    verification_instance = UserUniqueTokens(
        user=user,
        token=verification_token,
        token_type="Verification"
    )
    verification_instance.save()

    email = "Activitytracker.app@gmail.com"
    mail_title = "Activity Tracker Account Verification"
    recipient = [user.email.encode('utf8')]
    mail_message = 'Hello user %s. In order to verify your account click the following link: %s' \
                   % (user.get_username(), verification_url)

    send_mail(mail_title, mail_message, email, recipient, fail_silently=False)

    return HttpResponse(SUCCESS_MSG)


# Produce new random pass and send it with e-mail
def passwordforget(request):

    USER_NOT_EXISTS_MSG = 'No such User exists'
    SUCCESS_MSG = 'We have sent you an email with instructions on how to reset your password'

    if request.method != 'POST':
        return render(request, 'activitytracker/passforget.html')

    if User.objects.filter(username=request.POST['username']).count() == 0:
        return HttpResponse(USER_NOT_EXISTS_MSG)

    user = User.objects.get(username=request.POST['username'])
    characters = string.ascii_letters + string.digits
    passwordforget_token = ''.join(random.choice(characters) for _ in range(20))
    passwordforget_url = '%s/activitytracker/account/password_reset/%s' % (SERVER_URL, passwordforget_token)
    passwordforget_instance = UserUniqueTokens(
        user=user,
        token=passwordforget_token,
        token_type="PasswordReset"
    )
    passwordforget_instance.save()

    email = "Activitytracker.app@gmail.com"
    mail_title = "Activity Tracker Password Reset"
    recipient = [user.email.encode('utf8')]
    mail_message = 'Hello user %s. You have recently requested a password reset. Please follow this link in order to ' \
                   'start the process: %s' % (user.get_username(), passwordforget_url)

    send_mail(mail_title, mail_message, email, recipient, fail_silently=False)

    return HttpResponse(SUCCESS_MSG)

# If token is correct, it loads a proper page to reset the password
def password_reset(request, passwordreset_token):

    PASSWORD_MISMATCH_ERROR = "The password you entered don't match each other. Try again"
    SUCCESS_MSG = "Your password has been successfully updated"

    try:
        token_instance = UserUniqueTokens.objects.get(
            token=passwordreset_token,
            token_type="PasswordReset"
        )
        valid_token = True

    except ObjectDoesNotExist:
        valid_token = False

    if request.method != "POST" or not valid_token:
        return render(request,'activitytracker/password-reset.html',{'valid_token': valid_token})

    else:
        password = request.POST['password']
        repeated_password = request.POST['repeated_password']
        if password != repeated_password:
            return HttpResponseBadRequest(PASSWORD_MISMATCH_ERROR)

        user = token_instance.user
        user.set_password(password)
        user.save()
        return HttpResponse(SUCCESS_MSG)

# Updates the password to its new value. Differs from the "change password" action, since it doesn't require an old pass
def forgotten_password_update(request):
    pass

# view to handle the email verification
def email_verification(request, verification_token):

    try:
        verification_instance = UserUniqueTokens.objects.get(
            token=verification_token,
            token_type="Verification"
        )
        user = verification_instance.user
        user.is_active = True
        user.save()
        verification_instance.delete()
        success = True

    except ObjectDoesNotExist:
        success = False

    return render(request,'activitytracker/account-verification.html',
                  {'verification_successful': success}
                  )



# Handle settings options
@login_required
def settings(request):

    WRONG_PASS_MSG = 'The password you entered didnt match your current password'
    EMPTY_FIELDS_MSG = 'You cannot have a field empty'
    USERNAME_EXISTS_MSG = 'This username is already in use'
    BIRTHDAY_ERROR_MSG = 'You cannot be born in the future, duh!'
    PASS_MISSMATCH_MSG = 'Sorry the passwords you entered didnt match eachother'
    basic_routine_activities = [
        'Eating',
        'Working',
        'Commuting',
        'Education',
        'Sleeping'
    ]

    day_types = [
        'Weekdays',
        'Weekend'
    ]

    user = request.user

    if request.method == 'POST':

        if request.POST['settingAction'] == 'deleteaccount':

            if user.check_password(request.POST['password']):
                user.delete()
                return HttpResponseRedirect(reverse('login'))

            return HttpResponseBadRequest(WRONG_PASS_MSG)

        elif request.POST['settingAction'] == 'editinfo':

                old_username = user.get_username()
                user.username = request.POST['username']
                user.first_name = request.POST['firstname']
                user.last_name = request.POST['lastname']
                user.gender = request.POST['gender']
                user.date_of_birth = datetime.strptime(request.POST['birthday'], "%m/%d/%Y").date()

                if '' in (user.username, user.first_name, user.last_name, user.gender):
                    return HttpResponseBadRequest(EMPTY_FIELDS_MSG)

                if user.username != old_username and User.objects.filter(username=user.username).count() > 0:
                    return HttpResponseBadRequest(USERNAME_EXISTS_MSG)

                if user.date_of_birth > datetime.now().date():
                    return HttpResponseBadRequest(BIRTHDAY_ERROR_MSG)

                user.save()

                return HttpResponse(json.dumps({
                                            'username': user.get_username(),
                                            'fname': user.first_name,
                                            'lname': user.last_name,
                                            'email': user.email,
                                            'birthday': request.POST['birthday'],
                                            'gender': user.gender,
                                            }
                                        ),
                                        content_type='application/json'
                                    )

        elif request.POST['settingAction'] == 'passchange':

            if request.POST['new_password'] != request.POST['new_password_repeat']:
                return HttpResponseBadRequest(PASS_MISSMATCH_MSG)

            if user.has_usable_password():
                if not user.check_password(request.POST['old_password']):
                    return HttpResponseBadRequest(WRONG_PASS_MSG)

            user.set_password(request.POST['new_password'])
            user.save()

            return HttpResponseRedirect(reverse('login'))

    gender = '' if not user.gender else user.gender
    birth = '' if not user.date_of_birth else user.date_of_birth.strftime("%m/%d/%Y")

    providerDomValues = {}

    for provider in AVAILABLE_PROVIDERS:

        if user.social_auth.filter(provider=provider).count() == 0:
            providerDomValues[provider] = getAppManagementDomValues("Not Connected", provider)
            continue

        provider_object = eval(provider.title().replace('-', ''))(user.social_auth.get(provider=provider))
        providerDomValues[provider] = getAppManagementDomValues(provider_object.validate(), provider)

    basicRoutineActivities = list()

    for activity_name in basic_routine_activities:

            activity = Activity.objects.get(activity_name=activity_name)
            routine_times = list()

            for day_type in day_types:
                try:
                    routine_data = user.routine_set.get(activity=activity, day_type=day_type)
                except:
                    routine_times += ''
                    continue
                start_time = '' if not routine_data.start_time else routine_data.start_time
                end_time = '' if not routine_data.end_time else routine_data.end_time

                start_string = '' if not start_time else start_time.strftime('%H:%M')
                end_string = '' if not end_time else end_time.strftime('%H:%M')
                routine_times.append('%s - %s' % (start_string, end_string))

            basicRoutineActivities.append({
                'activity': activity.activity_name,
                'color': activity.category,
                'times': routine_times,
                'icon_classname': activity.icon_classname,
            })

    context = {'username': user.get_username(),
               'firstname': user.get_short_name(),
               'lastname': user.last_name,
               'email': user.email,
               'birth': birth,
               'gender': gender,
               'social_login': not user.has_usable_password(),
               'providerDomValues': providerDomValues,
               'basicRoutineActivities': basicRoutineActivities
               }

    return render(request, 'activitytracker/settings.html', context)


# Handler for the Places in Settings.html
@login_required
def places(request):

    user = request.user

    if request.method != "POST":
        return HttpResponseRedirect(reverse('settings'))

    if request.POST['setting'] in ('addPlace', 'editPlace'):

        name = request.POST['place_name']
        address = request.POST['address']
        lat = request.POST['lat']
        lng = request.POST['lng']

        if not name:
            return HttpResponseBadRequest('Empty')

        if request.POST['setting'] == "addPlace":
            a = Places(user=user,
                       place_name=name,
                       place_address=address,
                       place_lat=lat,
                       place_lng=lng
                       )

        else:
            a = user.places_set.get(place_id=request.POST['place_id'])
            a.place_name, a.place_address = name, address
            a.place_lat, a.place_lng = lat, lng

        try:
            a.save()
            return HttpResponse('ok')

        except IntegrityError:
            return HttpResponseBadRequest('Unique')

    elif request.POST['setting'] == "deletePlace":

        place = user.places_set.get(place_id=request.POST['place_id'])
        place.delete()
        return HttpResponse('ok')


def placestojson(request):

    user = request.user
    json_list = {"data": []}

    for p in user.places_set.all():
        json_list['data'].append({
            'id': p.place_id,
            'lat': p.place_lat,
            'lng': p.place_lng,
            'place_name': p.place_name,
            'place_address': p.place_address
        })

    return HttpResponse(json.dumps(json_list), content_type='application/json')



# Basic View, Gets called on "History" page load
@login_required
def index(request):

    user = request.user
    object_list = [i.object_name for i in user.object_set.all()] #for form
    friend_list = [i.friend_name for i in user.friend_set.all()] #for form

    activity_data = dict([(category, []) for ( _ , category) in Activity.CATEGORY_CHOICES])
    for activity in Activity.objects.all():
        activity_data[activity.get_category_display()].append(activity.activity_name)

    context = {
               'list_of_objects': object_list,
               'username': user.get_username(),
               'list_of_friends': friend_list,
               'activity_data': activity_data,
               'show_carousel_guide': False
    }

    if not user.logged_in_before:

        context['show_carousel_guide'] = True
        user.logged_in_before = True
        user.save()

    return render(request, 'activitytracker/index.html', context)



# Gets called on "Group common" click, to return grouped activities
def getgroupedactivities(request):

    user = request.user
    if len(request.POST['grouped_data']) == 0:
        return HttpResponse(json.dumps([]), content_type='application/json')

    ids = (request.POST['grouped_data']).split("_")
    instances = user.performs_set.filter(id__in=ids)
    json_list = list()

    if request.POST['box'] == "checked":

        entries = dict()

        for instance in instances:

            if instance.activity.activity_name in entries:
               entries[instance.activity.activity_name][0].end_date += instance.end_date - instance.start_date
               entries[instance.activity.activity_name][1] += '_%s' % str(instance.id)
               continue

            entries[instance.activity.activity_name] = [instance, str(instance.id)]

        for activity_name, activity_data in entries.iteritems():

            [instance, grouped_id] = activity_data

            json_list.append({
                'id': grouped_id,
                'start_date': instance.start_date.strftime('%Y%m%d%H%M'),
                'duration': instance.displayable_date(),
                'activity': instance.activity.activity_name,
                'colour': str(instance.activity.category),
                'icon_classname': instance.activity.icon_classname
            })

    else:
        for event in instances:
            json_list.append(
                            { 'id': event.id,
                               'start_date': event.start_date.strftime('%Y%m%d%H%M'),
                               'duration': event.displayable_date(),
                               'activity': event.activity.activity_name,
                               'colour': str(event.activity.category),
                               'icon_classname': event.activity.icon_classname
                            }
            )

    sort = request.POST['sort']

    if sort == "Activity":
        json_list = sorted(json_list, key=operator.itemgetter('activity', 'start_date'))
    elif sort == "Category":
        json_list = sorted(json_list, key=operator.itemgetter('colour', 'start_date'))
    else:
        json_list = sorted(json_list, key=operator.itemgetter('start_date'))

    return HttpResponse(json.dumps(json_list), content_type='application/json')


# Gets called each time an activity is added
def addactivity(request):

    DB_ERROR = 'Database Insertion Error. Check your fields and try again'
    FIELD_ERROR = 'Please fill up at least date and time fields correctly'
    DATE_ERROR = 'Activity cant end sooner than it began'

    if '' in (request.POST['start_date'],
              request.POST['end_date'],
              request.POST['start_time'],
              request.POST['end_time'],
              request.POST['name_of_activity']
              ):
        return HttpResponseBadRequest(FIELD_ERROR)

    user = request.user
    activity = Activity.objects.get(activity_name=request.POST['name_of_activity'])
    start_datetime = '%s %s:00' % (request.POST['start_date'], request.POST['start_time'])
    end_datetime = '%s %s:00' % (request.POST['end_date'], request.POST['end_time'])
    goal = request.POST['goal']
    goal_status = '' if 'goalstatus' not in request.POST else request.POST['goalstatus']
    result = request.POST['result']
    objects = request.POST['tool']
    friends = request.POST['friend_list']
    location_address = request.POST['location_address']
    location_lat = None if request.POST['lng'] == ''  else request.POST['lat']
    location_lng = None if request.POST['lng'] == '' else request.POST['lng']

    start_datetime = datetime.strptime(start_datetime, "%m/%d/%Y %H:%M:%S")
    end_datetime = datetime.strptime(end_datetime, "%m/%d/%Y %H:%M:%S")

    if start_datetime > end_datetime:
        return HttpResponseBadRequest(DATE_ERROR)

    instance = addActivityFromProvider(user=user,
                                       activity=activity,
                                       start_date=start_datetime,
                                       end_date=end_datetime,
                                       goal=goal,
                                       goal_status=goal_status,
                                       friends=friends,
                                       objects=objects,
                                       result=result,
                                       location_lat=location_lat,
                                       location_lng=location_lng,
                                       location_address=location_address
                                       )
    #print instance
    #except ValueError:
    #    return HttpResponseBadRequest(DB_ERROR)

    return HttpResponse(
        json.dumps(
            {
                'id': str(instance.id),
                'duration': instance.displayable_date(),
                'activity': instance.activity.activity_name,
                'colour': instance.activity.category
            }
        ),
        content_type='application/json'
    )



# Gets called each time a single activity is clicked
def showactivity(request, performs_identification):

    user = request.user
    details = user.performs_set.get(id=performs_identification)
    tools = ', '.join(object.object_name for object in details.using.all())
    start_date = details.start_date.strftime('%m/%d/%Y')
    end_date = details.end_date.strftime('%m/%d/%Y')
    end_time = details.end_date.strftime('%H:%M')
    start_time = details.start_date.strftime('%H:%M')

    try:
        provider_instance = PerformsProviderInfo.objects.get(instance=details)
    except ObjectDoesNotExist:
        provider_instance = None

    context = {'instance': details,
               'tools': tools,
               'start_t': start_time,
               'end_t': end_time,
               'end_date': end_date,
               'start_date': start_date,
               'color': colourDict[details.activity.category],
               'performs_provider_instance': provider_instance
               }

    return SimpleTemplateResponse('activitytracker/display-activity.html', context)


# Gets called when a grouped activity needs to be shown
def showgroupactivity(request, group_identification):

    user = request.user
    id_list = group_identification.split('_')
    events = user.performs_set.filter(id__in=id_list).order_by('start_date')
    activity_group = []

    for details in events:
        tools_string = ', '.join(str(t.object_name) for t in details.using.all())
        start_date = details.start_date.strftime('%m/%d/%Y')
        end_date = details.end_date.strftime('%m/%d/%Y')
        start_time = details.start_date.strftime('%H:%M')
        end_time = details.end_date.strftime('%H:%M')
        colour = colourDict[details.activity.category]

        try:
            provider_instance = PerformsProviderInfo.objects.get(instance=details)
        except ObjectDoesNotExist:
            provider_instance = None

        activity_group.append({'tools': tools_string,
                             'start_time': start_time,
                             'end_time': end_time,
                             'end_date': end_date,
                             'start_date': start_date,
                             'instance': details,
                             'performs_provider_instance': provider_instance
                             })

    activities = {'activity_list': activity_group,
                  'color': colour,
                  'total_grouped_activities': len(id_list)
                  }

    return SimpleTemplateResponse('activitytracker/display-group-activity.html',
                                  activities
                                  )

# Deletes an activity
def deleteactivity(request):

    activity = Performs.objects.get(id=request.POST['act_id'])
    activity.delete()

    return HttpResponse('Deleted')


# Gives all the activities as JSON
@login_required
def listallactivities(request):

    context = {'activity_list': Activity.objects.all()}

    return render(request,
                  'activitytracker/activitytable.html',
                  context
                  )



#Gets called when Edit button is clicked, to instantiate values of inputs in the template
def editactivity(request, performs_id):

    user = request.user
    instance = Performs.objects.get(id=int(performs_id))
    start_date = instance.start_date.strftime('%m/%d/%Y')
    end_date = instance.end_date.strftime('%m/%d/%Y')
    end_time = instance.end_date.strftime('%H:%M')
    start_time = instance.start_date.strftime('%H:%M')
    instance_object_list = [i.object_name for i in instance.using.all()]
    instance_friend_list = filter(None, instance.friends.split(","))

    object_list = [i.object_name for i in user.object_set.all()] #for form
    friend_list = [i.friend_name for i in user.friend_set.all()] #for form

    activity_data = dict([(category, []) for ( _ , category) in Activity.CATEGORY_CHOICES])
    for activity in Activity.objects.all():
        activity_data[activity.get_category_display()].append(activity.activity_name)

    context = {'instance': instance,
               'instance_object_list': instance_object_list,
               'instance_friend_list': instance_friend_list,
               'start_t': start_time,
               'end_t': end_time,
               'end_date': end_date,
               'start_date': start_date,
               'activity_data': activity_data,
               'list_of_objects': object_list,
               'list_of_friends': friend_list,
               'color': colourDict[instance.activity.category],
               }

    return SimpleTemplateResponse('activitytracker/edit-activity.html', context)


#Gets called on update activity
def updateactivity(request):

    DATE_ERROR_MSG = 'Activity cannot end sooner than it started'
    FIELD_ERROR_MSG = 'Please fill out all the fields correctly'

    user = request.user
    instance = Performs.objects.get(id=int(request.POST['the_id']))

    try:
        start_date = '%s %s:00' % (request.POST['start_date'], request.POST['start_time'])
        end_date = '%s %s:00' % (request.POST['end_date'], request.POST['end_time'])
        start_date = datetime.strptime(start_date, "%m/%d/%Y %H:%M:%S")
        end_date = datetime.strptime(end_date, "%m/%d/%Y %H:%M:%S")

        if start_date > end_date:
            return HttpResponseBadRequest(DATE_ERROR_MSG)

        activity = Activity.objects.get(activity_name=request.POST['name_of_activity'])
        friends = ','.join(list(set(request.POST['friend_list'].split(','))))
        objects = ','.join(list(set(request.POST['tool'].split(','))))
        location_address = request.POST['location_address']
        location_lat = request.POST['lat']
        location_lng = request.POST['lng']
        goal = request.POST['goal']
        result = request.POST['result']
        goal_status = None if not instance.goal else request.POST['goalstatus']

        instance.delete()

        instance = addActivityFromProvider(user=user,
                                           activity=activity,
                                           start_date=start_date,
                                           end_date=end_date,
                                           goal=goal,
                                           goal_status=goal_status,
                                           friends=friends,
                                           objects=objects,
                                           result=result,
                                           location_lat=location_lat,
                                           location_lng=location_lng,
                                           location_address=location_address
                                           )

    except ValueError:
        return HttpResponseBadRequest(FIELD_ERROR_MSG)

    return HttpResponse(
        json.dumps(
            {
                'id': str(instance.id),
                'duration': instance.displayable_date(),
                'activity': instance.activity.activity_name,
                'colour': instance.activity.category,
                'goal': instance.goal,
                'goal_status': instance.goal_status,
                'friends': instance.friends,
                'location_address': instance.location_address,
                'start_date': instance.start_date.strftime('%I:%M%p (%m/%d/%Y)'),
                'tools': ', '.join(t.object_name for t in instance.using.all()),
                'icon_classname': instance.activity.icon_classname,

            }
        ),
        content_type='application/json'
    )


# provides the JSON to the chart of Index Page
def chartdatajson(request):
    user = request.user

    if len(request.GET['chart_data']) == 0:
        return HttpResponse(json.dumps([]), content_type='application/json')

    ids = request.GET['chart_data'].split("_")
    instances = user.performs_set.filter(id__in=map(int, ids))

    chart_data = [
        {
            'label': category,
            'data': 0,
            'color': colourDict[colour]
        } for (colour, category) in Activity.CATEGORY_CHOICES
    ]

    for instance in instances:
        duration = instance.end_date - instance.start_date
        minutes = duration.seconds/60 + duration.days*24*60

        for index, category_dict in enumerate(chart_data):
            if category_dict['label'] == instance.activity.get_category_display():
                chart_data[index]['data'] += minutes
                break

    return HttpResponse(json.dumps(chart_data), content_type='application/json')

# Provides the event to the calendar
def eventstojson(request):

    user = request.user
    json_list = []

    for instance in user.performs_set.all():
        json_list.append({
            'id': instance.id,
            'start': instance.start_date.strftime("%Y-%m-%dT%H:%M:%S"),
            'allDay': False,
            'end': instance.end_date.strftime("%Y-%m-%dT%H:%M:%S"),
            'editable': False,
            'title': instance.activity.activity_name,
            'color': colourDict[instance.activity.category],
        })

    return HttpResponse(json.dumps(json_list), content_type='application/json')

# Gets called when calendar changes view
def displayperiod(request):

    user = request.user
    mode = request.POST['mode']

    if mode == "month":
        year = request.POST['year']
        month = request.POST['month']

        month_first_moment = datetime.strptime(
            '%s-%s-01 00:00:00' % (year, month),
            "%Y-%b-%d %H:%M:%S"
        )

        month_last_moment = datetime.strptime(
            '%s-%s-%s 23:59:59' % (year, month, str(calendar.monthrange(
                int(year),
                datetime.strptime(month, '%b').month)[1])
                                   ),
                "%Y-%b-%d %H:%M:%S"
        )

        instances = user.performs_set.filter(start_date__lte=month_last_moment,
                                             end_date__gte=month_first_moment
                                             )

    elif mode == "agendaDay":
        day = request.POST['day']
        year = request.POST['year']
        month = request.POST['month']

        day_first_moment = datetime.strptime('%s-%s-%s 00:00:00' % (year, month, day),
                                             "%Y-%b-%d %H:%M:%S"
                                             )

        day_last_moment = datetime.strptime('%s-%s-%s 23:59:59' % (year, month,day),
                                            "%Y-%b-%d %H:%M:%S"
                                            )

        instances = user.performs_set.filter(start_date__lte=day_last_moment,
                                             end_date__gte=day_first_moment
                                             )
    else:
        day = request.POST['day']
        year = request.POST['year']
        month = request.POST['month']

        day2 = request.POST['day2']
        year2 = request.POST['year2']
        month2 = request.POST['month2']

        week_first_moment = datetime.strptime('%s-%s-%s 00:00:00' % (year, month, day),
                                              "%Y-%b-%d %H:%M:%S"
                                              )

        week_last_moment = datetime.strptime('%s-%s-%s 23:59:59' % (year2, month2, day2),
                                             "%Y-%b-%d %H:%M:%S"
                                             )

        instances = user.performs_set.filter(start_date__lte=week_last_moment,
                                             end_date__gte=week_first_moment
                                             )

    ids = '_'.join(str(instance.id) for instance in instances)

    return HttpResponse(ids)


# Called to instantiate HTML and redirect to Goals Page
@login_required
def goals(request):

    user = request.user
    total_goals = len(user.performs_set.exclude(goal=""))

    return render(request,
                  'activitytracker/goals.html',
                  {
                      'username': user.get_username(),
                      'total_number': total_goals
                  }
                 )


# Feeds the jQuery.dataTable that is the table in the Goals page
def goalstojson(request):

    user = request.user
    json_list = {"data": []}
    activities = user.performs_set.exclude(goal="")

    for activity in activities:
        json_list['data'].append({
            'goal': activity.goal,
            'date': activity.start_date.strftime('%m/%d/%Y'),
            'activity': activity.activity.activity_name,
            'goal_status': activity.goal_status,
            'id': activity.id,
        })

    return HttpResponse(json.dumps(json_list), content_type='application/json')


# Gets called when any action from Goals.html is being performed
def goalhandler(request):

    DELETE_ERROR_MSG = 'Goal cant be empty! You can delete it though options'

    user = request.user
    setting = request.POST['setting']

    if setting == "deleteGoal":
        performs_instance = user.performs_set.get(id=request.POST['performs_id'])
        performs_instance.goal, performs_instance.goal_status = "", None
        performs_instance.save()
        return HttpResponse(len(user.performs_set.exclude(goal="")))

    elif setting == "updateGoal":
        updatedgoal = request.POST['data']
        updatedgoal_id = request.POST['performs_id']

        if updatedgoal == "":
            return HttpResponseBadRequest(DELETE_ERROR_MSG)

        performs_instance = user.performs_set.get(id=updatedgoal_id)
        performs_instance.goal = updatedgoal
        performs_instance.save()

        return HttpResponse('Ok')

    else:
        updategoalstatus_id = request.POST['performs_id']
        updategoalstatus_newstatus = request.POST['data']
        performs_instance = user.performs_set.get(id=updategoalstatus_id)
        performs_instance.goal_status = updategoalstatus_newstatus
        performs_instance.save()

        return HttpResponse('Ok')

# A json display of an activity that the user performs. Suitable for sync with other apps
def activitydetails(request, performs_id):

    user = request.user
    details = user.performs_set.get(id=performs_id)
    tools_string = ', '.join(t.object_name for t in details.using.all())

    json_list = {
        'id': details.id,
        'activity': details.activity.activity_name,
        'start_date': str(details.start_date),
        'end_date': str(details.end_date),
        'goal': details.goal,
        'goal_status': details.goal_status,
        'friends': details.friends,
        'tools': tools_string,
    }

    return HttpResponse(json.dumps(json_list), content_type='application/json')


# Loads the basic HTML of the Timeline Page
@login_required
def timeline(request):

    return render(
        request,
        'activitytracker/timeline.html',
        {
          'username': request.user.get_username()
        }
    )

 # Feeds the activities as json and paginates them to the html
def timeline_events_json(request):
    user = request.user

    total_events = user.performs_set.order_by('-start_date')
    paginator = Paginator(total_events, 10)
    requested_page = request.GET['page']
    json_list = []

    try:
        requested_events = paginator.page(requested_page)

        for instance in requested_events:
            tools_string = ', '.join(t.object_name for t in instance.using.all())
            start_date = instance.start_date.strftime('%I:%M%p (%m/%d/%Y)')
            json_entry = {
                'activity': instance.activity.activity_name,
                'start_date': start_date,
                'duration': instance.displayable_date(),
                'goal': instance.goal,
                'goal_status': instance.goal_status,
                'friends': instance.friends,
                'tools': tools_string,
                'result': instance.result,
                'colour': instance.activity.category,
                'id': instance.id,
                'location_address': instance.location_address,
                'icon_classname': instance.activity.icon_classname,
            }
            json_list.append(json_entry)

    except EmptyPage:
        pass

    return HttpResponse(json.dumps(json_list), content_type='application/json')


@login_required
def analytics_activities(request):
    user = request.user
    colourdict = {'black': 0, 'blue': 1, 'greenLight': 2,
                  'orange': 3, 'redDark': 4, 'purple': 5 }
    act_name_list = user.performs_set.values('activity__activity_name',
                                             'activity__category').order_by('activity__activity_name').distinct()
    activity_context_list = [[],[],[],[],[],[]]
    for activity in act_name_list:
        list_to_append = activity_context_list[colourdict[activity['activity__category']]]
        list_to_append.append(activity['activity__activity_name'])

    context_data = {
                    "Selfcare/Everyday Needs": activity_context_list[0],
                    "Communication/Socializing": activity_context_list[1],
                    "Sports/Fitness": activity_context_list[2],
                    "Fun/Leisure/Hobbies": activity_context_list[3],
                    "Responsibilities": activity_context_list[4],
                    "Transportation": activity_context_list[5],
                   }
    return render(request, 'activitytracker/analytics-activities.html',
                  {
                   'username': user.get_username(),
                   'activity_data': context_data,
                  }
    )


@login_required
def analytics_routine(request):

    user = request.user
    colourdict = {'black': 0, 'blue': 1, 'greenLight': 2,
                  'orange': 3, 'redDark': 4, 'purple': 5 }
    act_name_list = user.performs_set.values('activity__activity_name',
                                             'activity__category').order_by('activity__activity_name').distinct()
    activity_context_list = [[],[],[],[],[],[]]
    for activity in act_name_list:
        list_to_append = activity_context_list[colourdict[activity['activity__category']]]
        list_to_append.append(activity['activity__activity_name'])

    context_data = {
                    "Selfcare/Everyday Needs": activity_context_list[0],
                    "Communication/Socializing": activity_context_list[1],
                    "Sports/Fitness": activity_context_list[2],
                    "Fun/Leisure/Hobbies": activity_context_list[3],
                    "Responsibilities": activity_context_list[4],
                    "Transportation": activity_context_list[5],
                   }
    return render(request, 'activitytracker/analytics-routine.html',
                  {
                   'username': user.get_username(),
                   'activity_data': context_data,
                  }
    )


@login_required
def analytics_friends(request):
    user = request.user
    colourdict = {'black': 0, 'blue': 1, 'greenLight': 2,
                  'orange': 3, 'redDark': 4, 'purple': 5 }
    act_name_list = user.performs_set.values('activity__activity_name',
                                             'activity__category').order_by('activity__activity_name').distinct()
    activity_context_list = [[],[],[],[],[],[]]
    for activity in act_name_list:
        list_to_append = activity_context_list[colourdict[activity['activity__category']]]
        list_to_append.append(activity['activity__activity_name'])

    context_data = {
                    "Selfcare/Everyday Needs": activity_context_list[0],
                    "Communication/Socializing": activity_context_list[1],
                    "Sports/Fitness": activity_context_list[2],
                    "Fun/Leisure/Hobbies": activity_context_list[3],
                    "Responsibilities": activity_context_list[4],
                    "Transportation": activity_context_list[5],
                   }
    friend_context_list = [i.friend_name for i in user.friend_set.all()]
    return render(request, 'activitytracker/analytics-friends.html',
                  {
                   'username': user.get_username(),
                   'activity_data': context_data,
                   'friend_data': friend_context_list
                  }
    )

@login_required
def analytics_places(request):
    user = request.user
    context_data = [p.place_name for p in user.places_set.all()]
    return render(request, 'activitytracker/analytics-places.html',
                 {
                   'username': user.get_username(),
                   'places_data': context_data,
                  }
    )

@login_required
def analytics_goals(request):
    user = request.user
    colourdict = {'black': 0, 'blue': 1, 'greenLight': 2,
                  'orange': 3, 'redDark': 4, 'purple': 5 }
    act_name_list = user.performs_set.values('activity__activity_name',
                                             'activity__category').order_by('activity__activity_name').distinct()
    activity_context_list = [[],[],[],[],[],[]]
    for activity in act_name_list:
        list_to_append = activity_context_list[colourdict[activity['activity__category']]]
        list_to_append.append(activity['activity__activity_name'])

    context_data = {
                    "Selfcare/Everyday Needs": activity_context_list[0],
                    "Communication/Socializing": activity_context_list[1],
                    "Sports/Fitness": activity_context_list[2],
                    "Fun/Leisure/Hobbies": activity_context_list[3],
                    "Responsibilities": activity_context_list[4],
                    "Transportation": activity_context_list[5],
                   }

    return render(request, 'activitytracker/analytics-goals.html',
                  {
                   'username': user.get_username(),
                   'activity_data': context_data,
                  }
    )

@login_required
def analytics_objects(request):
    user = request.user

    colourdict = {'black': 0, 'blue': 1, 'greenLight': 2,
                  'orange': 3, 'redDark': 4, 'purple': 5 }
    act_name_list = user.performs_set.values('activity__activity_name',
                                             'activity__category').order_by('activity__activity_name').distinct()
    activity_context_list = [[],[],[],[],[],[]]
    for activity in act_name_list:
        list_to_append = activity_context_list[colourdict[activity['activity__category']]]
        list_to_append.append(activity['activity__activity_name'])

    context_data = {
                    "Selfcare/Everyday Needs": activity_context_list[0],
                    "Communication/Socializing": activity_context_list[1],
                    "Sports/Fitness": activity_context_list[2],
                    "Fun/Leisure/Hobbies": activity_context_list[3],
                    "Responsibilities": activity_context_list[4],
                    "Transportation": activity_context_list[5],
                   }
    object_context_list = []
    objects = user.object_set.all()
    for object in objects:
        object_context_list.append(object.object_name)
    return render(request, 'activitytracker/analytics-objects.html',
                  {
                   'username': user.get_username(),
                   'activity_data': context_data,
                   'object_data': object_context_list
                  }
    )

def updateonefriendmanyactivitiescharts(request):
    colourDict = {'black': "rgba(1, 1, 1, 0.8)",
                  'blue': "#578EBE",
                  'greenLight': "#99B433",
                  'orange': "#e09100",
                  'redDark': "rgb(148, 5, 37)",
                  'purple': "#800080"
    }
    user = request.user
    friend_selected = request.POST['friend']
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment).order_by('activity__category')
    chart_outer_data = collections.OrderedDict()
    chart_inner_data = collections.OrderedDict()
    count = 1

    for activity_instance in instances:
        if friend_selected in activity_instance.friends:
            if ((friend_selected == "") and (activity_instance.friends == "")) or ((friend_selected != "") and (activity_instance.friends != "")):
                try:
                    chart_inner_data[activity_instance.activity.get_category_display()]['count'] += 1
                    chart_inner_data[activity_instance.activity.get_category_display()]['time'] += activity_instance.end_date - activity_instance.start_date
                except KeyError:
                    chart_inner_data[activity_instance.activity.get_category_display()] = {}
                    chart_inner_data[activity_instance.activity.get_category_display()]['count'] = 1
                    chart_inner_data[activity_instance.activity.get_category_display()]['time'] = activity_instance.end_date - activity_instance.start_date
                    chart_inner_data[activity_instance.activity.get_category_display()]['color'] = colourDict[activity_instance.activity.category]
                try:
                    chart_outer_data[activity_instance.activity.activity_name]['count'] += 1
                    chart_outer_data[activity_instance.activity.activity_name]['time'] += activity_instance.end_date - activity_instance.start_date
                except KeyError:
                    chart_outer_data[activity_instance.activity.activity_name] = {}
                    chart_outer_data[activity_instance.activity.activity_name]['count'] = 1
                    chart_outer_data[activity_instance.activity.activity_name]['time'] = activity_instance.end_date - activity_instance.start_date
    json_list = [[], []]
    for key, value in chart_inner_data.iteritems():
        json_entry = {'Category': key ,
                      'Hours': round(value['time'].seconds/float(3600) + value['time'].days*float(24), 2),
                      'Instances': str(value['count']),
                      'Color': value['color'],
                      }
        json_list[0].append(json_entry)

    for key, value in chart_outer_data.iteritems():
        json_entry = {'Activity': key ,
                      'Timeorder': count,
                      'Instances': str(value['count']),
                      'Hours': round(value['time'].seconds/float(3600) + value['time'].days*float(24), 2),
                      'Category': Activity.objects.get(activity_name=key).get_category_display()
                      }
        json_list[1].append(json_entry)
        count += 1

    return HttpResponse(json.dumps(json_list), content_type='application/json')


def updateoneactivitymanyfriendscharts(request):
    user = request.user
    activity_selected = request.POST['activity']
    activity_object = Activity.objects.get(activity_name=activity_selected)
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment, activity=activity_object)

    chart_data = collections.OrderedDict()
    friends = [i.friend_name for i in user.friend_set.all()]
    count = 1
    barChart_data = []
    for activity_instance in instances:
        duration = activity_instance.end_date - activity_instance.start_date
        if activity_instance.friends != "":
            for friend in friends:
                if friend in activity_instance.friends:
                    dummy_dict = {
                                'Timeorder': count,
                                'Start_Date': activity_instance.start_date.strftime("%m/%d/%Y %H:%M"),
                                'Hours': round(duration.seconds/float(3600) + duration.days*float(24), 2),
                                'Friend': friend
                                }
                    barChart_data.append(dummy_dict)
                    try:
                        chart_data[friend]['count'] += 1
                        chart_data[friend]['time'] += activity_instance.end_date - activity_instance.start_date
                    except KeyError:
                        chart_data[friend] = {}
                        chart_data[friend]['count'] = 1
                        chart_data[friend]['time'] = activity_instance.end_date - activity_instance.start_date

        else:
            dummy_dict = {
                        'Timeorder': count,
                        'Start_Date': activity_instance.start_date.strftime("%m/%d/%Y %H:%M"),
                        'Hours': round(duration.seconds/float(3600) + duration.days*float(24), 2),
                        'Friend': 'Alone'
            }
            barChart_data.append(dummy_dict)
            try:
                chart_data['Alone']['count'] += 1
                chart_data['Alone']['time'] += activity_instance.end_date - activity_instance.start_date
            except KeyError:
                chart_data['Alone'] = {}
                chart_data['Alone']['count'] = 1
                chart_data['Alone']['time'] = activity_instance.end_date - activity_instance.start_date
        count += 1

    json_list = [[]]
    count = 1
    for key, value in chart_data.iteritems():
        json_entry = {'Friend': key ,
                      'Timeorder': count,
                      'Hours': round(value['time'].seconds/float(3600) + value['time'].days*float(24), 2),
                      'Instances': str(value['count']),
                      }
        json_list[0].append(json_entry)
        count += 1


    json_list.append(barChart_data)
    return HttpResponse(json.dumps(json_list), content_type='application/json')


def updateoneactivityonefriendchart(request):
    user = request.user
    activity_selected = request.POST['activity']
    friend_selected = request.POST['friend']
    activity_object = Activity.objects.get(activity_name=activity_selected)
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment, activity=activity_object)
    instances = instances.order_by('start_date')

    lineChart_data = []
    count = 1
    for activity_instance in instances:
        if friend_selected in activity_instance.friends:
            if ((friend_selected == "") and (activity_instance.friends == "")) or ((friend_selected != "") and (activity_instance.friends != "")):
                duration = activity_instance.end_date - activity_instance.start_date
                if activity_instance.goal != "":
                    if activity_instance.goal_status == "Reached":
                        goal_status_to_int = 3
                    elif activity_instance.goal_status == "Failed":
                        goal_status_to_int = 1
                    else:
                        goal_status_to_int = 2
                else:
                    goal_status_to_int = 0

                lineChart_data.append({
                                       'Timeorder': count,
                                       'Start_Date': activity_instance.start_date.strftime("%m/%d/%Y %H:%M"),
                                       'Hours': round(duration.seconds/float(3600) + duration.days*float(24), 2),
                                       'Goal_Status': goal_status_to_int
                                      })
                count += 1

    return HttpResponse(json.dumps(lineChart_data), content_type='application/json')


def updatemanyactivitiesmanyfriendschart(request):
    user = request.user
    friends = [i.friend_name for i in user.friend_set.all()]
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment)

    chart_data = {}
    for activity_instance in instances:
        if activity_instance.friends != "":
            for friend in friends:
                if friend in activity_instance.friends:
                    try:
                        chart_data[activity_instance.activity.activity_name][friend]['count'] += 1
                        chart_data[activity_instance.activity.activity_name][friend]['time'] += activity_instance.end_date - activity_instance.start_date
                    except KeyError:
                        try:
                            chart_data[activity_instance.activity.activity_name]
                        except KeyError:
                            chart_data[activity_instance.activity.activity_name] = {}
                        chart_data[activity_instance.activity.activity_name][friend] = {}
                        chart_data[activity_instance.activity.activity_name][friend]['count'] = 1
                        chart_data[activity_instance.activity.activity_name][friend]['time'] = activity_instance.end_date - activity_instance.start_date

        else:

            try:
                chart_data[activity_instance.activity.activity_name]['Alone']['count'] += 1
                chart_data[activity_instance.activity.activity_name]['Alone']['time'] += activity_instance.end_date - activity_instance.start_date
            except KeyError:
                try:
                    chart_data[activity_instance.activity.activity_name]
                except KeyError:
                    chart_data[activity_instance.activity.activity_name] = {}
                chart_data[activity_instance.activity.activity_name]['Alone'] = {}
                chart_data[activity_instance.activity.activity_name]['Alone']['count'] = 1
                chart_data[activity_instance.activity.activity_name]['Alone']['time'] = activity_instance.end_date - activity_instance.start_date

    json_list = []
    for key, value in chart_data.iteritems():
        for inner_key, inner_value in value.iteritems():
            json_entry = {'Activity': key ,
                          'Friend': inner_key,
                          'Instances': str(inner_value['count']),
                          'Hours': round(inner_value['time'].seconds/float(3600) + inner_value['time'].days*float(24), 2),
                          }
            json_list.append(json_entry)

    return HttpResponse(json.dumps(json_list), content_type='application/json')

def updatefriendsbanner(request):
    user = request.user
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    friend_selected = request.POST['friend']
    total_time_spent_with_friends = datetime.now() - datetime.now()
    activity_selected = request.POST['activity']
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")

    if activity_selected == "all":
        instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment)
    else:
        activity_object = Activity.objects.get(activity_name=activity_selected)
        instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment, activity=activity_object)

    if friend_selected == 'all':
        total_activities_with_friends = len(instances.exclude(friends__exact=""))
        for activity_instance in instances.exclude(friends__exact=""):
            total_time_spent_with_friends += activity_instance.end_date - activity_instance.start_date
            dummy_datetime_object = activity_instance

    else:
        total_activities_with_friends = 0
        for activity_instance in instances:
            if ((friend_selected == "") and (activity_instance.friends == "")) or ((friend_selected != "") and (activity_instance.friends != "")):
                if friend_selected in activity_instance.friends:
                    total_time_spent_with_friends += activity_instance.end_date - activity_instance.start_date
                    total_activities_with_friends += 1
                    dummy_datetime_object = activity_instance

    try:
        dummy_datetime_object.start_date = datetime.now()
        dummy_datetime_object.end_date = datetime.now() + total_time_spent_with_friends
        printable_time = dummy_datetime_object.displayable_date()
    except UnboundLocalError:
        printable_time = "0d0h0m"

    total_activities = len(instances)
    try:
        percentage_of_activities_with_friends = round(total_activities_with_friends/float(total_activities), 3)*100
    except ZeroDivisionError:
        percentage_of_activities_with_friends = 0
    json_response = {
                    'total_activities': total_activities,
                    'total_activities_done_with_friends': total_activities_with_friends,
                    'percentage_of_activities_with_friends': percentage_of_activities_with_friends,
                    'total_time_spent_with_friends': printable_time
                    }
    return HttpResponse(json.dumps(json_response),content_type="application/json")


##################################################################################

def updateoneobjectmanyactivitiescharts(request):
    colourDict = {'black': "rgba(1, 1, 1, 0.8)",
                  'blue': "#578EBE",
                  'greenLight': "#99B433",
                  'orange': "#e09100",
                  'redDark': "rgb(148, 5, 37)",
                  'purple': "#800080"
    }
    user = request.user
    object_selected = request.POST['object']
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment).order_by('activity__category')
    chart_outer_data = collections.OrderedDict()
    chart_inner_data = collections.OrderedDict()
    count = 1
    for activity_instance in instances:
        objects_string = ', '.join(str(t.object_name) for t in activity_instance.using.all())
        if object_selected in objects_string:
            if ((object_selected == "") and (objects_string == "")) or ((object_selected != "") and (objects_string != "")):
                try:
                    chart_inner_data[activity_instance.activity.get_category_display()]['count'] += 1
                    chart_inner_data[activity_instance.activity.get_category_display()]['time'] += activity_instance.end_date - activity_instance.start_date
                except KeyError:
                    chart_inner_data[activity_instance.activity.get_category_display()] = {}
                    chart_inner_data[activity_instance.activity.get_category_display()]['count'] = 1
                    chart_inner_data[activity_instance.activity.get_category_display()]['time'] = activity_instance.end_date - activity_instance.start_date
                    chart_inner_data[activity_instance.activity.get_category_display()]['color'] = colourDict[activity_instance.activity.category]
                try:
                    chart_outer_data[activity_instance.activity.activity_name]['count'] += 1
                    chart_outer_data[activity_instance.activity.activity_name]['time'] += activity_instance.end_date - activity_instance.start_date
                except KeyError:
                    chart_outer_data[activity_instance.activity.activity_name] = {}
                    chart_outer_data[activity_instance.activity.activity_name]['count'] = 1
                    chart_outer_data[activity_instance.activity.activity_name]['time'] = activity_instance.end_date - activity_instance.start_date
    json_list = [[], []]
    for key, value in chart_inner_data.iteritems():
        json_entry = {'Category': key ,
                      'Hours': round(value['time'].seconds/float(3600) + value['time'].days*float(24), 2),
                      'Instances': str(value['count']),
                      'Color': value['color'],
                      }
        json_list[0].append(json_entry)

    for key, value in chart_outer_data.iteritems():
        json_entry = {'Activity': key ,
                      'Timeorder': count,
                      'Instances': str(value['count']),
                      'Hours': round(value['time'].seconds/float(3600) + value['time'].days*float(24), 2),
                      'Category': Activity.objects.get(activity_name=key).get_category_display()
                      }
        json_list[1].append(json_entry)
        count += 1

    return HttpResponse(json.dumps(json_list), content_type='application/json')


def updateoneactivitymanyobjectscharts(request):
    user = request.user
    activity_selected = request.POST['activity']
    activity_object = Activity.objects.get(activity_name=activity_selected)
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment, activity=activity_object)

    chart_data = collections.OrderedDict()
    all_objects = list(o.object_name for o in user.object_set.all())
    count = 1
    barChart_data = []
    for activity_instance in instances:
        duration = activity_instance.end_date - activity_instance.start_date
        activity_objects_string = ', '.join(str(t.object_name) for t in activity_instance.using.all())
        if activity_objects_string != "":
            for obj in all_objects:
                if obj in activity_objects_string:
                    dummy_dict = {
                                'Timeorder': count,
                                'Start_Date': activity_instance.start_date.strftime("%m/%d/%Y %H:%M"),
                                'Hours': round(duration.seconds/float(3600) + duration.days*float(24), 2),
                                'Object': obj
                                }
                    barChart_data.append(dummy_dict)
                    try:
                        chart_data[obj]['count'] += 1
                        chart_data[obj]['time'] += activity_instance.end_date - activity_instance.start_date
                    except KeyError:
                        chart_data[obj] = {}
                        chart_data[obj]['count'] = 1
                        chart_data[obj]['time'] = activity_instance.end_date - activity_instance.start_date

        else:
            dummy_dict = {
                        'Timeorder': count,
                        'Start_Date': activity_instance.start_date.strftime("%m/%d/%Y %H:%M"),
                        'Hours': round(duration.seconds/float(3600) + duration.days*float(24), 2),
                        'Object': 'No Object used'
            }
            barChart_data.append(dummy_dict)
            try:
                chart_data['No Object used']['count'] += 1
                chart_data['No Object used']['time'] += activity_instance.end_date - activity_instance.start_date
            except KeyError:
                chart_data['No Object used'] = {}
                chart_data['No Object used']['count'] = 1
                chart_data['No Object used']['time'] = activity_instance.end_date - activity_instance.start_date
        count += 1

    json_list = [[]]
    count = 1
    for key, value in chart_data.iteritems():
        json_entry = {'Object': key ,
                      'Timeorder': count,
                      'Hours': round(value['time'].seconds/float(3600) + value['time'].days*float(24), 2),
                      'Instances': str(value['count']),
                      }
        json_list[0].append(json_entry)
        count += 1


    json_list.append(barChart_data)
    return HttpResponse(json.dumps(json_list), content_type='application/json')


def updateoneactivityoneobjectchart(request):
    user = request.user
    activity_selected = request.POST['activity']
    object_selected = request.POST['object']
    activity_object = Activity.objects.get(activity_name=activity_selected)
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment, activity=activity_object)
    instances = instances.order_by('start_date')

    lineChart_data = []
    count = 1
    for activity_instance in instances:
        activity_objects_string = ', '.join(str(t.object_name) for t in activity_instance.using.all())
        if object_selected in activity_objects_string:
            if ((object_selected == "") and (activity_objects_string == "")) or ((object_selected != "") and (activity_objects_string != "")):
                duration = activity_instance.end_date - activity_instance.start_date
                if activity_instance.goal != "":
                    if activity_instance.goal_status == "Reached":
                        goal_status_to_int = 3
                    elif activity_instance.goal_status == "Failed":
                        goal_status_to_int = 1
                    else:
                        goal_status_to_int = 2
                else:
                    goal_status_to_int = 0

                lineChart_data.append({
                                       'Timeorder': count,
                                       'Start_Date': activity_instance.start_date.strftime("%m/%d/%Y %H:%M"),
                                       'Hours': round(duration.seconds/float(3600) + duration.days*float(24), 2),
                                       'Goal_Status': goal_status_to_int
                                      })
                count += 1

    return HttpResponse(json.dumps(lineChart_data), content_type='application/json')


def updatemanyactivitiesmanyobjectschart(request):
    user = request.user
    all_objects = list(o.object_name for o in user.object_set.all())
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment)

    chart_data = {}
    for activity_instance in instances:
        activity_objects_string = ', '.join(str(t.object_name) for t in activity_instance.using.all())
        if activity_objects_string != "":
            for obj in all_objects:
                if obj in activity_objects_string:
                    try:
                        chart_data[activity_instance.activity.activity_name][obj]['count'] += 1
                        chart_data[activity_instance.activity.activity_name][obj]['time'] += activity_instance.end_date - activity_instance.start_date
                    except KeyError:
                        try:
                            chart_data[activity_instance.activity.activity_name]
                        except KeyError:
                            chart_data[activity_instance.activity.activity_name] = {}
                        chart_data[activity_instance.activity.activity_name][obj] = {}
                        chart_data[activity_instance.activity.activity_name][obj]['count'] = 1
                        chart_data[activity_instance.activity.activity_name][obj]['time'] = activity_instance.end_date - activity_instance.start_date

        else:

            try:
                chart_data[activity_instance.activity.activity_name]['No Objects used']['count'] += 1
                chart_data[activity_instance.activity.activity_name]['No Objects used']['time'] += activity_instance.end_date - activity_instance.start_date
            except KeyError:
                try:
                    chart_data[activity_instance.activity.activity_name]
                except KeyError:
                    chart_data[activity_instance.activity.activity_name] = {}
                chart_data[activity_instance.activity.activity_name]['No Objects used'] = {}
                chart_data[activity_instance.activity.activity_name]['No Objects used']['count'] = 1
                chart_data[activity_instance.activity.activity_name]['No Objects used']['time'] = activity_instance.end_date - activity_instance.start_date

    json_list = []
    for key, value in chart_data.iteritems():
        for inner_key, inner_value in value.iteritems():
            json_entry = {'Activity': key ,
                          'Object': inner_key,
                          'Instances': str(inner_value['count']),
                          'Hours': round(inner_value['time'].seconds/float(3600) + inner_value['time'].days*float(24), 2),
                          }
            json_list.append(json_entry)

    return HttpResponse(json.dumps(json_list), content_type='application/json')

def updateobjectsbanner(request):
    user = request.user
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    object_selected = request.POST['object']
    total_time_with_objects = datetime.now() - datetime.now()
    activity_selected = request.POST['activity']
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")

    if activity_selected == "all":
        instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment)
    else:
        activity_object = Activity.objects.get(activity_name=activity_selected)
        instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment, activity=activity_object)

    if object_selected == 'all':
        total_activities_with_objects = len(instances.exclude(using=None))
        for activity_instance in instances.exclude(using=None):
            total_time_with_objects += activity_instance.end_date - activity_instance.start_date
            dummy_datetime_object = activity_instance

    else:
        total_activities_with_objects = 0
        for activity_instance in instances:
            activity_objects_string = ', '.join(str(t.object_name) for t in activity_instance.using.all())
            if ((object_selected == "") and (activity_objects_string == "")) or ((object_selected != "") and (activity_objects_string != "")):
                if object_selected in activity_objects_string:
                    total_time_with_objects += activity_instance.end_date - activity_instance.start_date
                    total_activities_with_objects += 1
                    dummy_datetime_object = activity_instance

    try:
        dummy_datetime_object.start_date = datetime.now()
        dummy_datetime_object.end_date = datetime.now() + total_time_with_objects
        printable_time = dummy_datetime_object.displayable_date()
    except UnboundLocalError:
        printable_time = "0d0h0m"

    total_activities = len(instances)
    try:
        percentage_of_activities_with_objects = round(total_activities_with_objects/float(total_activities), 3)*100
    except ZeroDivisionError:
        percentage_of_activities_with_objects = 0
    json_response = {
                    'total_activities': total_activities,
                    'total_activities_done_with_objects': total_activities_with_objects,
                    'percentage_of_activities_with_objects': percentage_of_activities_with_objects,
                    'total_time_with_objects': printable_time
                    }
    return HttpResponse(json.dumps(json_response),content_type="application/json")

def updateactivitydonutchart(request):
    user = request.user
    activity_selected = request.POST['activity']
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    if activity_selected != "all":
        activity_object = Activity.objects.get(activity_name=activity_selected)
        instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment, activity=activity_object)
    else:
        instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment)

    chart_data = {}
    for activity_instance in instances:
        if activity_instance.goal != "":
            if activity_instance.goal_status == "InProgress":
                activity_instance.goal_status = "In Progress"
            try:
                chart_data[activity_instance.goal_status] += 1
            except KeyError:
                chart_data[activity_instance.goal_status] = 1
        else:
            try:
                chart_data["No Goal set"] += 1
            except KeyError:
                chart_data["No Goal set"] = 1

    json_list = []
    for key, value in chart_data.iteritems():
        json_entry = {'Goal Status': key,
                      'Instances': value,
                      }
        json_list.append(json_entry)
    return HttpResponse(json.dumps(json_list), content_type='application/json')


def updateactivityandcategorybarchart(request):
    user = request.user
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment)

    chart_data_activities = {}
    chart_data_categories = {}
    for activity_instance in instances:
        if activity_instance.goal != "":
            if activity_instance.goal_status == "InProgress":
                activity_instance.goal_status = "In Progress"
            try:
                chart_data_categories[activity_instance.activity.get_category_display()][activity_instance.goal_status] += 1
            except KeyError:
                try:
                    chart_data_categories[activity_instance.activity.get_category_display()]
                except KeyError:
                    chart_data_categories[activity_instance.activity.get_category_display()] = {}
                chart_data_categories[activity_instance.activity.get_category_display()][activity_instance.goal_status] = 1
            try:
                chart_data_activities[activity_instance.activity.activity_name][activity_instance.goal_status] += 1
            except KeyError:
                try:
                    chart_data_activities[activity_instance.activity.activity_name]
                except KeyError:
                    chart_data_activities[activity_instance.activity.activity_name] = {}
                chart_data_activities[activity_instance.activity.activity_name][activity_instance.goal_status] = 1
        else:
            try:
                chart_data_categories[activity_instance.activity.get_category_display()]["No Goal set"] += 1
            except KeyError:
                try:
                    chart_data_categories[activity_instance.activity.get_category_display()]
                except KeyError:
                    chart_data_categories[activity_instance.activity.get_category_display()] = {}
                chart_data_categories[activity_instance.activity.get_category_display()]["No Goal set"] = 1

            try:
                chart_data_activities[activity_instance.activity.activity_name]["No Goal set"] += 1
            except KeyError:
                try:
                    chart_data_activities[activity_instance.activity.activity_name]
                except KeyError:
                    chart_data_activities[activity_instance.activity.activity_name] = {}
                chart_data_activities[activity_instance.activity.activity_name]["No Goal set"] = 1

    json_list = [[], []]
    for key, value in chart_data_activities.iteritems():
        for inner_key, inner_value in value.iteritems():
            json_entry = {'Activity': key,
                          'Goal Status': inner_key,
                          'Instances': inner_value,
                          }
            json_list[0].append(json_entry)

    for key, value in chart_data_categories.iteritems():
        for inner_key, inner_value in value.iteritems():
            json_entry = {'Category': key,
                          'Goal Status': inner_key,
                          'Instances': inner_value,
                          }
            json_list[1].append(json_entry)

    return HttpResponse(json.dumps(json_list), content_type='application/json')


def updateactivityandobjectbubblechart(request):
    user = request.user
    all_objects = list(o.object_name for o in user.object_set.all())
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment)

    chart_data = {}
    for activity_instance in instances:
        activity_objects_string = ', '.join(str(t.object_name) for t in activity_instance.using.all())
        if activity_instance.goal_status == "InProgress":
                activity_instance.goal_status = "In Progress"
        if activity_objects_string != "":
            for obj in all_objects:
                if obj in activity_objects_string:
                    if activity_instance.goal != "":
                        try:
                            chart_data[activity_instance.activity.activity_name][obj][activity_instance.goal_status] += 1
                        except KeyError:
                            try:
                                chart_data[activity_instance.activity.activity_name]
                            except KeyError:
                                chart_data[activity_instance.activity.activity_name] = {}
                            try:
                                chart_data[activity_instance.activity.activity_name][obj]
                            except KeyError:
                                chart_data[activity_instance.activity.activity_name][obj] = {}
                            chart_data[activity_instance.activity.activity_name][obj][activity_instance.goal_status] = 1
                    else:
                        try:
                            chart_data[activity_instance.activity.activity_name][obj]["No Goal set"] += 1
                        except KeyError:
                            try:
                                chart_data[activity_instance.activity.activity_name]
                            except KeyError:
                                chart_data[activity_instance.activity.activity_name] = {}
                            try:
                                chart_data[activity_instance.activity.activity_name][obj]
                            except KeyError:
                                chart_data[activity_instance.activity.activity_name][obj] = {}
                            chart_data[activity_instance.activity.activity_name][obj]["No Goal set"] = 1
        else:
            if activity_instance.goal != "":
                try:
                    chart_data[activity_instance.activity.activity_name]['No Objects used'][activity_instance.goal_status] += 1
                except KeyError:
                    try:
                        chart_data[activity_instance.activity.activity_name]
                    except KeyError:
                        chart_data[activity_instance.activity.activity_name] = {}
                    try:
                        chart_data[activity_instance.activity.activity_name]["No Objects used"]
                    except KeyError:
                        chart_data[activity_instance.activity.activity_name]["No Objects used"] = {}
                    chart_data[activity_instance.activity.activity_name]["No Objects used"][activity_instance.goal_status] = 1
            else:
                try:
                    chart_data[activity_instance.activity.activity_name]["No Objects used"]["No Goal set"] += 1
                except KeyError:
                    try:
                        chart_data[activity_instance.activity.activity_name]
                    except KeyError:
                        chart_data[activity_instance.activity.activity_name] = {}
                    try:
                        chart_data[activity_instance.activity.activity_name]["No Objects used"]
                    except KeyError:
                        chart_data[activity_instance.activity.activity_name]["No Objects used"] = {}
                    chart_data[activity_instance.activity.activity_name]["No Objects used"]["No Goal set"] = 1
    json_list = []
    for key, value in chart_data.iteritems():
        for inner_key, inner_value in value.iteritems():
            for status, status_instances in inner_value.iteritems():
                json_entry = {'Activity': key ,
                              'Object': inner_key,
                              'Goal Status': status,
                              'Instances': status_instances
                              }
                json_list.append(json_entry)
    return HttpResponse(json.dumps(json_list), content_type='application/json')


def updateactivitysandfriendbubblechart(request):
    user = request.user
    all_friends = [i.friend_name for i in user.friend_set.all()]
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment)

    chart_data = {}
    for activity_instance in instances:
        if activity_instance.friends != "":
            for friend in all_friends:
                if friend in activity_instance.friends:
                    if activity_instance.goal != "":
                        if activity_instance.goal_status == "InProgress":
                            activity_instance.goal_status = "In Progress"
                        try:
                            chart_data[activity_instance.activity.activity_name][friend][activity_instance.goal_status] += 1
                        except KeyError:
                            try:
                                chart_data[activity_instance.activity.activity_name]
                            except KeyError:
                                chart_data[activity_instance.activity.activity_name] = {}
                            try:
                                chart_data[activity_instance.activity.activity_name][friend]
                            except KeyError:
                                chart_data[activity_instance.activity.activity_name][friend] = {}
                            chart_data[activity_instance.activity.activity_name][friend][activity_instance.goal_status] = 1
                    else:
                        try:
                            chart_data[activity_instance.activity.activity_name][friend]["No Goal set"] += 1
                        except KeyError:
                            try:
                                chart_data[activity_instance.activity.activity_name]
                            except KeyError:
                                chart_data[activity_instance.activity.activity_name] = {}
                            try:
                                chart_data[activity_instance.activity.activity_name][friend]
                            except KeyError:
                                chart_data[activity_instance.activity.activity_name][friend] = {}
                            chart_data[activity_instance.activity.activity_name][friend]["No Goal set"] = 1
        else:
            if activity_instance.goal != "":
                try:
                    chart_data[activity_instance.activity.activity_name]['Alone'][activity_instance.goal_status] += 1
                except KeyError:
                    try:
                        chart_data[activity_instance.activity.activity_name]
                    except KeyError:
                        chart_data[activity_instance.activity.activity_name] = {}
                    try:
                        chart_data[activity_instance.activity.activity_name]["Alone"]
                    except KeyError:
                        chart_data[activity_instance.activity.activity_name]["Alone"] = {}
                    chart_data[activity_instance.activity.activity_name]["Alone"][activity_instance.goal_status] = 1
            else:
                try:
                    chart_data[activity_instance.activity.activity_name]["Alone"]["No Goal set"] += 1
                except KeyError:
                    try:
                        chart_data[activity_instance.activity.activity_name]
                    except KeyError:
                        chart_data[activity_instance.activity.activity_name] = {}
                    try:
                        chart_data[activity_instance.activity.activity_name]["Alone"]
                    except KeyError:
                        chart_data[activity_instance.activity.activity_name]["Alone"] = {}
                    chart_data[activity_instance.activity.activity_name]["Alone"]["No Goal set"] = 1
    json_list = []
    for key, value in chart_data.iteritems():
        for inner_key, inner_value in value.iteritems():
            for status, status_instances in inner_value.iteritems():
                json_entry = {'Activity': key ,
                              'Friend': inner_key,
                              'Goal Status': status,
                              'Instances': status_instances
                              }
                json_list.append(json_entry)
    return HttpResponse(json.dumps(json_list), content_type='application/json')

def updategoalsbanner(request):
    user = request.user
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    analysis_selected = request.POST['analysis']
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment)
    total_activities = len(instances)
    goals_reached = 0
    if analysis_selected == 'Activities & Categories':
        total_goals_set = len(instances.exclude(goal__exact=""))
        for activity_instance in instances.exclude(goal__exact=""):
            if activity_instance.goal_status == "Reached":
                goals_reached += 1
    elif analysis_selected == "Activity/Object":
        total_goals_set = len(instances.exclude(goal__exact="").exclude(using=None))
        for activity_instance in instances.exclude(goal__exact="").exclude(using=None):
            if activity_instance.goal_status == "Reached":
                goals_reached += 1
    else:
        total_goals_set = len(instances.exclude(goal__exact="").exclude(friends__exact=""))
        for activity_instance in instances.exclude(goal__exact="").exclude(friends__exact=""):
            if activity_instance.goal_status == "Reached":
                goals_reached += 1

    try:
        percentage_of_goals_reached = round(goals_reached/float(total_goals_set), 3)*100
    except ZeroDivisionError:
        percentage_of_goals_reached = 0
    json_response = {
                    'total_activities': total_activities,
                    'total_goals_set': total_goals_set,
                    'percentage_of_goals_reached': percentage_of_goals_reached,
                    }
    return HttpResponse(json.dumps(json_response),content_type="application/json")


def updateactivitiesinplacedonutchart(request):
    colourDict = {'black': "rgba(1, 1, 1, 0.8)",
                  'blue': "#578EBE",
                  'greenLight': "#99B433",
                  'orange': "#e09100",
                  'redDark': "rgb(148, 5, 37)",
                  'purple': "#800080"
    }

    pinColourDict = {'black': "black",
                     'blue': "blue",
                     'greenLight': "green",
                     'orange': "orange",
                     'redDark': "red",
                     'purple': "purple"
    }
    user = request.user
    radius_selected = request.POST['radius']
    place_selected = request.POST['place']

    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment).order_by('activity__category')
    chart_outer_data = collections.OrderedDict()
    chart_inner_data = collections.OrderedDict()
    json_list = [[], [], [], []]
    count = 1

    for activity_instance in instances:
        if activity_instance.location_address != "":
            if placesNearActivity(user, activity_instance, place_selected, radius_selected) != [] or place_selected == "all":
                json_list[2].append({'activity': activity_instance.activity.activity_name,
                                     'start_date': activity_instance.start_date.strftime("%m/%d/%Y %H:%M"),
                                     'duration': activity_instance.displayable_date(),
                                     'pinColor': pinColourDict[activity_instance.activity.category],
                                     'lat':activity_instance.location_lat,
                                     'lng':activity_instance.location_lng
                })


                try:
                    chart_inner_data[activity_instance.activity.get_category_display()]['count'] += 1
                    chart_inner_data[activity_instance.activity.get_category_display()]['time'] += activity_instance.end_date - activity_instance.start_date
                except KeyError:
                    chart_inner_data[activity_instance.activity.get_category_display()] = {}
                    chart_inner_data[activity_instance.activity.get_category_display()]['count'] = 1
                    chart_inner_data[activity_instance.activity.get_category_display()]['time'] = activity_instance.end_date - activity_instance.start_date
                    chart_inner_data[activity_instance.activity.get_category_display()]['color'] = colourDict[activity_instance.activity.category]
                try:
                    chart_outer_data[activity_instance.activity.activity_name]['count'] += 1
                    chart_outer_data[activity_instance.activity.activity_name]['time'] += activity_instance.end_date - activity_instance.start_date
                except KeyError:
                    chart_outer_data[activity_instance.activity.activity_name] = {}
                    chart_outer_data[activity_instance.activity.activity_name]['count'] = 1
                    chart_outer_data[activity_instance.activity.activity_name]['time'] = activity_instance.end_date - activity_instance.start_date

    # Return the data necessary for the inner ring of the double-donut chart (categories)
    for key, value in chart_inner_data.iteritems():
        json_entry = {'Category': key ,
                      'Hours': round(value['time'].seconds/float(3600) + value['time'].days*float(24), 2),
                      'Instances': str(value['count']),
                      'Color': value['color'],
                      }
        json_list[0].append(json_entry)

    # Return the data necessary for the outer ring of the double-donut chart (activities)
    for key, value in chart_outer_data.iteritems():
        json_entry = {'Activity': key ,
                      'Timeorder': count,
                      'Instances': str(value['count']),
                      'Hours': round(value['time'].seconds/float(3600) + value['time'].days*float(24), 2),
                      'Category': Activity.objects.get(activity_name=key).get_category_display()
                      }
        json_list[1].append(json_entry)
        count += 1

    # Also return the place or places so to pinpoint them on the Google Map
    if place_selected == "all" or place_selected == "Everywhere else":
        for p in user.places_set.all():
            json_list[3].append({
                'Place': p.place_name,
                'lat': p.place_lat,
                'lng': p.place_lng}
            )
    else:
        p = user.places_set.get(place_name=place_selected)
        json_list[3].append({
                'Place': p.place_name,
                'lat': p.place_lat,
                'lng': p.place_lng}
        )

    return HttpResponse(json.dumps(json_list), content_type='application/json')


def updateplacesbanner(request):
    user = request.user
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    place_selected = request.POST['place']
    radius_selected = request.POST['radius']
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment)

    total_time_spent_near_places = datetime.now() - datetime.now()
    total_activities_near_places = 0

    for activity_instance in instances:
        if activity_instance.location_address != "":
            if placesNearActivity(user, activity_instance, place_selected, radius_selected) != []:
                    total_time_spent_near_places += activity_instance.end_date - activity_instance.start_date
                    total_activities_near_places += 1
                    dummy_datetime_object = activity_instance

    try:
        dummy_datetime_object.start_date = datetime.now()
        dummy_datetime_object.end_date = datetime.now() + total_time_spent_near_places
        printable_time = dummy_datetime_object.displayable_date()
    except UnboundLocalError:
        printable_time = "0d0h0m"

    total_activities = len(instances)
    try:
        percentage_of_activities_near_places = round(total_activities_near_places/float(total_activities), 3)*100
    except ZeroDivisionError:
        percentage_of_activities_near_places = 0
    json_response = {
                    'total_activities': total_activities,
                    'total_activities_done_near_places': total_activities_near_places,
                    'percentage_of_activities_near_places': percentage_of_activities_near_places,
                    'total_time_spent_near_places': printable_time
                    }
    return HttpResponse(json.dumps(json_response),content_type="application/json")

##################################################################################

def updateallplacesbarchart(request):
    colourDict = {'black': "rgba(1, 1, 1, 0.8)",
                  'blue': "#578EBE",
                  'greenLight': "#99B433",
                  'orange': "#e09100",
                  'redDark': "rgb(148, 5, 37)",
                  'purple': "#800080"
    }
    user = request.user
    radius_selected = request.POST['radius']

    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment)
    all_places_data = {}
    json_list = []

    for activity_instance in instances:
        if activity_instance.location_address != "":
            places_that_contain_activity = placesNearActivity(user, activity_instance, 'all', radius_selected)
            if places_that_contain_activity != []:
                for place_name in places_that_contain_activity:
                    try:
                        all_places_data[place_name][activity_instance.activity.get_category_display()]['count'] += 1
                        all_places_data[place_name][activity_instance.activity.get_category_display()]['time'] += activity_instance.end_date - activity_instance.start_date
                    except KeyError:
                        try:
                            all_places_data[place_name]
                        except KeyError:
                            all_places_data[place_name] = {}
                        try:
                            all_places_data[place_name][activity_instance.activity.get_category_display()]
                        except KeyError:
                            all_places_data[place_name][activity_instance.activity.get_category_display()] = {}
                        all_places_data[place_name][activity_instance.activity.get_category_display()]['count'] = 1
                        all_places_data[place_name][activity_instance.activity.get_category_display()]['time'] = activity_instance.end_date - activity_instance.start_date
                        all_places_data[place_name][activity_instance.activity.get_category_display()]['color'] = colourDict[activity_instance.activity.category]
            else:
                try:
                    all_places_data["Everywhere else"][activity_instance.activity.get_category_display()]['count'] += 1
                    all_places_data["Everywhere else"][activity_instance.activity.get_category_display()]['time'] += activity_instance.end_date - activity_instance.start_date
                except KeyError:
                    try:
                        all_places_data["Everywhere else"]
                    except KeyError:
                        all_places_data["Everywhere else"] = {}
                    try:
                        all_places_data["Everywhere else"][activity_instance.activity.get_category_display()]
                    except KeyError:
                        all_places_data["Everywhere else"][activity_instance.activity.get_category_display()] = {}
                    all_places_data["Everywhere else"][activity_instance.activity.get_category_display()]['count'] = 1
                    all_places_data["Everywhere else"][activity_instance.activity.get_category_display()]['time'] = activity_instance.end_date - activity_instance.start_date
                    all_places_data["Everywhere else"][activity_instance.activity.get_category_display()]['color'] = colourDict[activity_instance.activity.category]

    for place_name, place_data in all_places_data.iteritems():
        for category_name, category_data in place_data.iteritems():
                json_entry = {'Place': place_name,
                              'Category': category_name ,
                              'Hours': round(category_data['time'].seconds/float(3600) + category_data['time'].days*float(24), 2),
                              'Instances': str(category_data['count']),
                              'Color': category_data['color'],
                              }
                json_list.append(json_entry)
    return HttpResponse(json.dumps(json_list), content_type='application/json')


def updateallactivitiescharts(request):
    colourDict = {'black': "rgba(1, 1, 1, 0.8)",
                  'blue': "#578EBE",
                  'greenLight': "#99B433",
                  'orange': "#e09100",
                  'redDark': "rgb(148, 5, 37)",
                  'purple': "#800080"
    }
    user = request.user
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment).order_by('activity__category')
    chart_outer_data = collections.OrderedDict()
    chart_inner_data = collections.OrderedDict()
    count = 1

    for activity_instance in instances:

        # Data for Activity Donut (outer)
        try:
            chart_inner_data[activity_instance.activity.get_category_display()]['count'] += 1
            chart_inner_data[activity_instance.activity.get_category_display()]['time'] += activity_instance.end_date - activity_instance.start_date
        except KeyError:
            chart_inner_data[activity_instance.activity.get_category_display()] = {}
            chart_inner_data[activity_instance.activity.get_category_display()]['count'] = 1
            chart_inner_data[activity_instance.activity.get_category_display()]['time'] = activity_instance.end_date - activity_instance.start_date
            chart_inner_data[activity_instance.activity.get_category_display()]['color'] = colourDict[activity_instance.activity.category]

        # Data for Category Donut (inner)
        try:
            chart_outer_data[activity_instance.activity.activity_name]['count'] += 1
            chart_outer_data[activity_instance.activity.activity_name]['time'] += activity_instance.end_date - activity_instance.start_date
        except KeyError:
            chart_outer_data[activity_instance.activity.activity_name] = {}
            chart_outer_data[activity_instance.activity.activity_name]['count'] = 1
            chart_outer_data[activity_instance.activity.activity_name]['time'] = activity_instance.end_date - activity_instance.start_date

    json_list = [[], []]
    for key, value in chart_inner_data.iteritems():
        json_entry = {'Category': key ,
                      'Hours': round(value['time'].seconds/float(3600) + value['time'].days*float(24), 2),
                      'Instances': str(value['count']),
                      'Color': value['color'],
                      }
        json_list[0].append(json_entry)

    for key, value in chart_outer_data.iteritems():
        json_entry = {'Activity': key ,
                      'Timeorder': count,
                      'Instances': str(value['count']),
                      'Interval': assignDurationInterval(value['time']),
                      'Hours': round(value['time'].seconds/float(3600) + value['time'].days*float(24), 2),
                      'Category': Activity.objects.get(activity_name=key).get_category_display()
                      }
        json_list[1].append(json_entry)
        count += 1

    return HttpResponse(json.dumps(json_list), content_type='application/json')

def updatesingleactivitycharts(request):
    user = request.user
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    activity_selected = request.POST['activity']
    activity_object = Activity.objects.get(activity_name=activity_selected)
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")
    instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment, activity=activity_object)

    dummy_iterator = range_first_moment
    timeaxis_activity_data = {}
    timeaxis_category_data = {}
    json_list = [[], []]
    while dummy_iterator < range_last_moment:
        timeaxis_activity_data[dummy_iterator.strftime("%m/%d/%Y")] = {}
        timeaxis_activity_data[dummy_iterator.strftime("%m/%d/%Y")]['count'] = 0
        timeaxis_activity_data[dummy_iterator.strftime("%m/%d/%Y")]['time'] = datetime.now() - datetime.now()

        timeaxis_category_data[dummy_iterator.strftime("%m/%d/%Y")] = {}
        timeaxis_category_data[dummy_iterator.strftime("%m/%d/%Y")]['count'] = 0
        timeaxis_category_data[dummy_iterator.strftime("%m/%d/%Y")]['time'] = datetime.now() - datetime.now()

        dummy_iterator += timedelta(days=1)

    # Data for Activity Series in Chart
    for activity_instance in instances:
        time_index = activity_instance.start_date
        while time_index < activity_instance.end_date:
            timeaxis_activity_data[time_index.strftime("%m/%d/%Y")]['count'] += 1

            done = False
            while not done:
                end_of_current_day = datetime.strptime(time_index.strftime("%m/%d/%Y") + ' 23:59:59', "%m/%d/%Y %H:%M:%S")
                if activity_instance.end_date <= end_of_current_day:
                    timeaxis_activity_data[time_index.strftime("%m/%d/%Y")]['time'] += activity_instance.end_date - activity_instance.start_date
                    done = True
                else:
                    timeaxis_activity_data[time_index.strftime("%m/%d/%Y")]['time'] += end_of_current_day - activity_instance.start_date
                    activity_instance.start_date = end_of_current_day + timedelta(seconds=1)
                time_index += timedelta(days=1)

    # Data for Category Series in Chart
    category_selected = activity_object.category
    category_instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment, activity__category=category_selected)
    for activity_instance in category_instances:
        time_index = activity_instance.start_date
        while time_index < activity_instance.end_date:
            timeaxis_category_data[time_index.strftime("%m/%d/%Y")]['count'] += 1

            done = False
            while not done:
                end_of_current_day = datetime.strptime(time_index.strftime("%m/%d/%Y") + ' 23:59:59', "%m/%d/%Y %H:%M:%S")
                if activity_instance.end_date <= end_of_current_day:
                    timeaxis_category_data[time_index.strftime("%m/%d/%Y")]['time'] += activity_instance.end_date - activity_instance.start_date
                    done = True
                else:
                    timeaxis_category_data[time_index.strftime("%m/%d/%Y")]['time'] += end_of_current_day - activity_instance.start_date
                    activity_instance.start_date = end_of_current_day + timedelta(seconds=1)
                time_index += timedelta(days=1)


    for key, value in timeaxis_activity_data.iteritems():
        json_list[0].append({
                        'Date': key,
                        'Series': activity_selected,
                        'Instances': value['count'],
                        'Hours': round(value['time'].seconds/float(3600) + value['time'].days*float(24), 2),
        })

    for key, value in timeaxis_category_data.iteritems():
        json_list[0].append({
                        'Date': key,
                        'Series': activity_object.get_category_display(),
                        'Instances': value['count'],
                        'Hours': round(value['time'].seconds/float(3600) + value['time'].days*float(24), 2),
        })

    # Here begins the code for the 2nd Chart -- the lineChart
    instances = instances.order_by('start_date')
    count = 1
    for activity_instance in instances:
        duration = activity_instance.end_date - activity_instance.start_date
        if activity_instance.goal != "":
            if activity_instance.goal_status == "Reached":
                goal_status_to_int = 3
            elif activity_instance.goal_status == "Failed":
                goal_status_to_int = 1
            else:
                goal_status_to_int = 2
        else:
            goal_status_to_int = 0

        json_list[1].append({
                               'Timeorder': count,
                               'Start_Date': activity_instance.start_date.strftime("%m/%d/%Y %H:%M"),
                               'Hours': round(duration.seconds/float(3600) + duration.days*float(24), 2),
                               'Goal_Status': goal_status_to_int
                              })
        count += 1

    return HttpResponse(json.dumps(json_list), content_type='application/json')


def updateactivitiesbanner(request):
    user = request.user
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    total_time_spent = datetime.now() - datetime.now()
    activity_selected = request.POST['activity']
    range_first_moment = datetime.strptime(datestart + '00:00:00', "%m/%d/%Y %H:%M:%S")
    range_last_moment = datetime.strptime(dateend + ' 23:59:59', " %m/%d/%Y %H:%M:%S")

    if activity_selected == "all":
        instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment)
        try:
            extra_mutable_analytic = round(len(instances.values('activity__activity_name').distinct())/float(len(instances)),3)*100
        except ZeroDivisionError:
            extra_mutable_analytic = 0
    else:
        activity_object = Activity.objects.get(activity_name=activity_selected)
        instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment, activity=activity_object)
        category_instances = user.performs_set.filter(start_date__lte=range_last_moment, end_date__gte=range_first_moment, activity__category=activity_object.category)
        try:
            extra_mutable_analytic = round(len(instances)/float(len(category_instances)), 3)*100
        except ZeroDivisionError:
            extra_mutable_analytic = 0


    for activity_instance in instances:
        total_time_spent += activity_instance.end_date - activity_instance.start_date
        dummy_datetime_object = activity_instance

    try:
        dummy_datetime_object.start_date = datetime.now()
        dummy_datetime_object.end_date = datetime.now() + total_time_spent
        printable_time = dummy_datetime_object.displayable_date()
    except UnboundLocalError:
        printable_time = "0d0h0m"

    total_activities = len(instances)
    json_response = {
                    'total_activities': total_activities,
                    'extra_mutable_analytic': extra_mutable_analytic,
                    'total_time_spent': printable_time
                    }
    return HttpResponse(json.dumps(json_response),content_type="application/json")


def social_login(request, action):
    return render(request, 'activitytracker/social-login.html',{'action': action})

def syncProviderActivities(request, provider):
    social_instance = request.user.social_auth.get(provider=provider)
    provider_object = eval(provider.title().replace('-', ''))(social_instance)

    return HttpResponse(provider_object.fetchData())


def routineSettings(request, setting='show'):

    TIME_ERROR = 'You cannot start earlier than you finish. The update will not be performed'
    basic_routine_activities = [
        'Eating',
        'Working',
        'Commuting',
        'Education',
        'Sleeping'
    ]

    user = request.user

    json_response = {
            'timeline_data': {},
            'input_data': []
        }

    if not setting:

        for activity_name in basic_routine_activities:
            activity = Activity.objects.get(activity_name=activity_name)
            json_response['input_data'].append({
                'activity': activity.activity_name,
                'color': activity.category,
                'icon_classname': activity.icon_classname,
            })

        for activity in Routine.objects.filter(user=user):
            pass

        return HttpResponse(
            json.dumps(json_response),
            content_type="application/json"
        )

    if setting == 'insert_more':

        for activity in Activity.objects.all().order_by('activity_name'):
            if activity.activity_name not in basic_routine_activities:
                json_response['input_data'].append({
                    'activity': activity.activity_name,
                    'color': activity.category,
                    'icon_classname': activity.icon_classname,
                })

        for activity in Routine.objects.filter(user=user):
            pass

        return HttpResponse(
            json.dumps(json_response),
            content_type="application/json"
        )

    elif setting == "configure_periods":

        day_type = request.POST['day_type']
        routine_activity = Activity.objects.get(activity_name=request.POST['activity'])

        if (request.POST['start_time'] and request.POST['end_time']):
            if request.POST['start_time'] > request.POST['end_time']:
                return HttpResponseBadRequest(TIME_ERROR)

        start_time = None if not request.POST['start_time'] \
            else datetime.strptime(request.POST['start_time'] + ':00', "%H:%M:%S")
        end_time = None if not request.POST['end_time'] \
            else datetime.strptime(request.POST['end_time'] + ':00', "%H:%M:%S")

        if user.routine_set.filter(day_type=day_type,
                                   activity=routine_activity
                                   ).count() > 0:

            instance = user.routine_set.get(
                day_type=day_type,
                activity=routine_activity
            )
            instance.start_time = start_time
            instance.end_time = end_time

        else:
            instance = Routine(
                user=user,
                activity=routine_activity,
                start_time=start_time,
                end_time=end_time,
                day_type=day_type
            )

        instance.save()
        return HttpResponse('Ok')


    return HttpResponse('Ok')


def updateallroutinecharts(request):

    user = request.user
    day_type_requested = request.POST['day_type']
    datestart = (request.POST['range']).split('-')[0]
    dateend = (request.POST['range']).split('-')[1]
    range_left = chosen_start = datetime.strptime(datestart, "%m/%d/%Y ")
    range_right = chosen_end = datetime.strptime(dateend, " %m/%d/%Y")
    routine = request.POST['routine'].replace('-',' ')
    routine_activity = Activity.objects.get(activity_name=routine)
    chart_data = collections.OrderedDict()
    print routine
    while True:

        if range_left > range_right:
            break

        day_type = "Weekdays" if range_left.weekday() <= 4 else "Weekend"

        if day_type_requested in ("Weekdays", "Weekend"):
            if day_type_requested != day_type:
                range_left += timedelta(days=1)
                continue

        try:
            routine_range = user.routine_set.get(
                activity=routine_activity,
                day_type=day_type
            )
        except ObjectDoesNotExist:
            range_left += timedelta(days=1)
            continue

        try:
            routine_start = datetime.combine(range_left, routine_range.start_time)
            routine_end = datetime.combine(range_left, routine_range.end_time)
        except:
            range_left += timedelta(days=1)
            continue

        background_actions = user.performs_set.filter(
            start_date__lte=routine_end,
            end_date__gte=routine_start
        )

        for action in background_actions:

            action_start = action.start_date
            action_end = action.end_date

            if (routine_start < action_start) and (routine_end > action_end) :
                intersection_time = action_end - action_start
                rest_time = action_end - action_end         # It is 0 of course


            elif (routine_start < action_start) and (routine_end <= action_end):
                intersection_time = routine_end - action_start
                rest_time = action_start - routine_start + action_end - routine_end

            elif (routine_start >= action_start) and (routine_end > action_end):
                intersection_time = action_end - routine_start
                rest_time = routine_start - action_start + routine_end - action_end

            else:
                intersection_time  = routine_end - routine_start
                rest_time = routine_start - action_start + action_end - routine_end

            try:
                chart_data[action.activity.activity_name]['count'] += 1
                chart_data[action.activity.activity_name]['intersection_time'] += intersection_time
                chart_data[action.activity.activity_name]['rest_time'] += rest_time

            except KeyError:
                chart_data[action.activity.activity_name] = {}
                chart_data[action.activity.activity_name]['count'] = 1
                chart_data[action.activity.activity_name]['intersection_time'] = intersection_time
                chart_data[action.activity.activity_name]['rest_time'] = rest_time

        range_left += timedelta(days=1)

    json_list = []
    for key, value in chart_data.iteritems():
        json_entries = [

            {'Action': key ,
            'Instances': str(value['count']),
            'Hours': round(value['intersection_time'].seconds/float(3600) + value['intersection_time'].days*float(24), 2),
            'Timeslice': 'Routine Metric Overlap',
            'OrderByTime': round(value['intersection_time'].seconds/float(3600) + value['intersection_time'].days*float(24), 2),
            'OrderByInstances': str(value['count']),
            },
            {'Action': key ,
            'Instances': str(user.performs_set.filter(
                start_date__lte=chosen_end,
                end_date__gte=chosen_start,
                activity=Activity.objects.get(activity_name=key)
            ).count() - (value['count'])),
            'Hours': round(value['rest_time'].seconds/float(3600) + value['rest_time'].days*float(24), 2),
            'Timeslice': 'Routine Metric Disjointedness',
            'OrderByTime': round(value['intersection_time'].seconds/float(3600) + value['intersection_time'].days*float(24), 2),
            'OrderByInstances': str(value['count']),
            },


        ]
        json_list += json_entries

    print json.dumps(json_list)
    return HttpResponse(json.dumps(json_list), content_type='application/json')