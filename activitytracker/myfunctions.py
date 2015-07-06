from math import radians, cos, sin, asin, sqrt
import requests
from social.apps.django_app.default.models import *
from activitytracker.models import *
from django.http import HttpResponse, HttpResponseBadRequest
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime, timedelta
from pygeocoder import Geocoder
from config import *
from tweetpony import APIError
import tweetpony


def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6367 * c
    return km

def addActivityFromProvider(user, goal, goal_status, friends, objects, result, location_lat, location_lng,
                            location_address, start_date, end_date, activity):

    performs_instance = Performs(user=user, activity=activity, friends=friends, goal=goal, goal_status=goal_status,
             location_address=location_address, location_lat=location_lat, location_lng=location_lng,
             start_date=start_date, end_date=end_date, result=result)
    performs_instance.save()

    for friend in friends.split(','):
        try:
            user.friend_set.get(friend_name=friend)
        except ObjectDoesNotExist:
            if not friend:
                continue
            instance = Friend(friend_name=friend, friend_of_user=user)
            instance.save()

    for tool in objects.split(','):
        try:
            object_instance = user.object_set.get(object_name=tool)
        except ObjectDoesNotExist:
            if not tool:
                continue
            object_instance = Object(object_name=tool, object_of_user=user)
            object_instance.save()
        performs_instance.using.add(object_instance)

    return performs_instance


def createActivityLinks(provider, instance, provider_instance_id, url ):
    if createActivityLinks:
        link_instance = PerformsProviderInfo(provider=provider, instance=instance,
                                             provider_instance_id=str(provider_instance_id), provider_instance_url=url)
        link_instance.save()
    return 'Done'



def placesNearActivity(user, activity, place, radius):

    places_returned_list = []
    if place == "all":
        all_places = [p for p in user.places_set.all()]
        for p in all_places:
            if haversine(p.place_lat,p.place_lng, activity.location_lat, activity.location_lng) <= float(radius):
                places_returned_list.append(p.place_name)
    elif place == "Everywhere else":
        all_places = [p for p in user.places_set.all()]
        for p in all_places:
            if haversine(p.place_lat,p.place_lng, activity.location_lat, activity.location_lng) <= float(radius):
                return []

        places_returned_list.append("Everywhere else")
    else:
        place_object = user.places_set.get(place_name=place)
        if haversine(place_object.place_lat, place_object.place_lng, activity.location_lat, activity.location_lng) <= float(radius):
            places_returned_list.append(place_object.place_name)
    return places_returned_list


def assignDurationInterval(duration):
    if duration.days > 0:
        return "> 24"

    if duration.seconds > 36000:
        return "10-24"
    elif duration.seconds > 18000:
        return "5-10"
    elif duration.seconds > 7200:
        return "2-5"
    elif duration.seconds > 3600:
        return "1-2"
    elif duration.seconds > 1800:
        return "0.5-1"
    else:
        return "0-0.5"


def syncRunkeeperActivities(user):
    # function that will fetch us the ids based on the url and headers we provided. Returns the list passed + the new ids
    def fetchRunkeeperFitnessActivityIds(passed_url, passed_headers):
        list_of_ids = []
        next_page_exists = True
        current_url = passed_url
        current_headers = passed_headers
        while next_page_exists:
            r = requests.get(current_url, headers=current_headers)
            # If activities were returned OR activities have been modified (we need it only on the 1st iteration)
            if r.status_code != 304:
                try:
                    # try removing this header but only if it was present.
                    current_headers.pop("If-Modified-Since")
                    # If it wasn't just 'pass'
                except KeyError:
                    pass

                rest_response_json = r.json()
                if not rest_response_json['items']:
                    return []
                for activity in rest_response_json['items']:
                    list_of_ids.append(activity['uri'].split("/fitnessActivities/")[1])
                    try:
                        current_url = 'http://api.runkeeper.com' + rest_response_json['next']
                    except KeyError:
                        next_page_exists = False
            else:
                # if status = 304 that means that we had an 'if-modified' check and nothing was modified
                # so we force the iteration to stop
                return []

        return list_of_ids
    # End of Function 1 ------------------ Start of function 2

    # function that will get the detailed info for each activity and put them into the database
    def insertRunkeeperFitnessActivities(token, id_list):
        url = 'http://api.runkeeper.com/fitnessActivities/'
        headers = {  'Host': 'api.runkeeper.com',
                     'Authorization': 'Bearer ' + str(token),
                     'Accept': 'application/vnd.com.runkeeper.FitnessActivity+json',
        }

        for runkeeper_id in id_list:
            current_url = url + str(runkeeper_id)
            # fetch details of activity
            r = requests.get(current_url, headers=headers).json()
            activity = Activity.objects.get(activity_name=r['type'])
            start_date = datetime.strptime(r['start_time'],'%a, %d %b %Y %H:%M:%S')
            end_date = start_date + timedelta(seconds=r['duration'])
            object = r['equipment']
            result = ''
            try:
                distance = str(int(round(r['total_distance'])))
                result += 'Covered ' + distance + ' Metres. '
            except KeyError:
                pass
            try:
                calories = str(int(round(r['total_calories'])))
                result += 'Burned ' + calories + ' Calories.'
            except KeyError:
                pass
            try:
                location_lat = float(r['path'][0]['latitude'])
                location_lng = float(r['path'][0]['longitude'])
                location_address = str(Geocoder.reverse_geocode(r['path'][0]['latitude'],r['path'][0]['longitude'])[0])
            except:
                location_lat = None
                location_lng = None
                location_address = ""

            # if object != none and it's not registered under the user, register it
            if user.object_set.filter(object_name=object).count() == 0 and object != "None":
                a = Object(object_name=object, object_of_user=user)
                a.save()

            # if activity already existed
            if PerformsProviderInfo.objects.filter(provider='runkeeper', provider_instance_id=str(runkeeper_id)).count() > 0:
                p = PerformsProviderInfo.objects.get(provider='runkeeper', provider_instance_id=str(runkeeper_id))
                performs_instance = p.instance
                performs_instance.activity = activity
                performs_instance.start_date = start_date
                performs_instance.end_date = end_date
                performs_instance.location_lat = location_lat
                performs_instance.location_lng = location_lng
                performs_instance.location_address = location_address
                performs_instance.result = result
                performs_instance.save()
                if object == "None":
                    continue
                object_object = user.object_set.get(object_name=object)
                if len(performs_instance.using.all()) == 1 and performs_instance.using.all()[0] in ["readmill", "Stationary Bike", "Elliptical", "Row Machine"]:
                    performs_instance.using.remove()
                    performs_instance.using.add(object_object)
                else:
                    performs_instance.using.add(object_object)
                performs_instance.save()
            # if activity didnt exist, we need to create an instance
            else:
                performs_instance = Performs(user=user, activity=activity, friends='', goal='', goal_status=None,
                                             location_address=location_address, location_lat=location_lat,
                                             location_lng=location_lng, start_date=start_date, end_date=end_date,
                                             result=result)
                performs_instance.save()
                if object != "None":
                    object_object = user.object_set.get(object_name=object)
                    performs_instance.using.add(object_object)
                    performs_instance.save()

                createActivityLinks('runkeeper', performs_instance, str(runkeeper_id), r['activity'] )

        return
    # End of Function 2 ----------------------------- Start of function for sleep activities

    def fetchAndInsertRunkeeperSleepActivities(passed_url, passed_headers):
        next_page_exists = True
        current_url = passed_url
        current_headers = passed_headers
        while next_page_exists:
            r = requests.get(current_url, headers=current_headers)
            # If activities were returned OR activities have been modified (we need it only on the 1st iteration)
            if r.status_code != 304:
                try:
                    # try removing this header but only if it was present.
                    current_headers.pop("If-Modified-Since")
                    # If it wasn't just 'pass'
                except KeyError:
                    pass

                rest_response_json = r.json()
                if not rest_response_json['items']:
                    return 0
                for activity in rest_response_json['items']:
                    runkeeper_id = activity['uri'].split("/sleep/")[1]
                    activity_name = Activity.objects.get(activity_name="Sleeping")
                    start_date = datetime.strptime(activity['timestamp'],'%a, %d %b %Y %H:%M:%S')
                    end_date = start_date + timedelta(seconds=activity['total_sleep']*60)
                    hours_of_sleep = activity['total_sleep']/60
                    if hours_of_sleep <= 4.0:
                        result = "Got only a bit of energy back"
                    elif hours_of_sleep <= 6.5:
                        result = "Rested, but not fully"
                    else:
                        result = "Had an almost perfectly fulfilling sleep"


                    # if activity already existed
                    if PerformsProviderInfo.objects.filter(provider='runkeeper', provider_instance_id=str(runkeeper_id)).count() > 0:
                        p = PerformsProviderInfo.objects.get(provider='runkeeper', provider_instance_id=str(runkeeper_id))
                        performs_instance = p.instance
                        # The only editable thing is the duration. So we only change that
                        performs_instance.end_date = end_date
                        performs_instance.result = result
                        performs_instance.save()
                    # if activity didnt exist, we need to create an instance
                    else:
                        performs_instance = Performs(user=user, activity=activity_name, friends='', goal='', goal_status=None,
                                                     location_address="", location_lat=None, location_lng=None,
                                                     start_date=start_date, end_date=end_date, result=result)
                        performs_instance.save()
                        try:
                            a = user.object_set.get(object_name='RunKeeper')
                        except ObjectDoesNotExist:
                            a = Object(object_name='RunKeeper', object_of_user=user)
                            a.save()
                        performs_instance.using.add(a)
                        performs_instance.save()
                        p = PerformsProviderInfo(provider='runkeeper', instance=performs_instance, provider_instance_id=str(runkeeper_id))
                        p.save()

                    try:
                        current_url = 'http://api.runkeeper.com' + rest_response_json['next']
                    except KeyError:
                        next_page_exists = False
            else:
                # if status = 304 that means that we had an 'if-modified' check and nothing was modified
                # so we force the iteration to stop
                return 0

        return 1


    # main
    social_auth_instance = user.social_auth.get(provider='runkeeper')
    access_token = social_auth_instance.extra_data['access_token']
    url = 'http://api.runkeeper.com/fitnessActivities'
    headers = {  'Host': 'api.runkeeper.com',
                 'Authorization': 'Bearer '+ str(access_token),
                 'Accept': 'application/vnd.com.runkeeper.FitnessActivityFeed+json',
    }

    # If it's not the first time we are syncing activities. We get the new activities that have happened after our last
    # call + any old activity that has been modified after out last call.
    try:
        last_updated = social_auth_instance.extra_data['last_updated']
        partition_barrier = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        # we get the activities that were modified after the time of the last sync. The previous changes are already migrated
        last_updated_url_for_activities = url + '?modifiedNoEarlierThan=' + partition_barrier
        last_updated_headers_for_activities = headers.copy()
        last_updated_headers_for_activities['If-Modified-Since'] = datetime.strptime(last_updated,"%Y-%m-%d %H:%M:%S").strftime('%a, %d %b %Y %H:%M:%S GMT')
        runkeeper_activity_id_list = fetchRunkeeperFitnessActivityIds(last_updated_url_for_activities, last_updated_headers_for_activities)
    # Field "last_updated" is not present. Thus we will ask for all the activities
    except KeyError:
        runkeeper_activity_id_list = fetchRunkeeperFitnessActivityIds(url, headers)
    print runkeeper_activity_id_list
    insertRunkeeperFitnessActivities(access_token, runkeeper_activity_id_list)

    # End for Fitness Activities, start of sleep activities
    url = 'http://api.runkeeper.com/sleep'
    headers = {  'Host': 'api.runkeeper.com',
                 'Authorization': 'Bearer '+ str(access_token),
                 'Accept': 'application/vnd.com.runkeeper.SleepSetFeed+json',
    }
    try:
        last_updated = social_auth_instance.extra_data['last_updated']
        partition_barrier = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        # we get the activities that were modified after the time of the last sync. The previous changes are already migrated
        last_updated_url_for_activities = url + '?modifiedNoEarlierThan=' + partition_barrier
        last_updated_headers_for_activities = headers.copy()
        last_updated_headers_for_activities['If-Modified-Since'] = datetime.strptime(last_updated,"%Y-%m-%d %H:%M:%S").strftime('%a, %d %b %Y %H:%M:%S GMT')
        sleep_activity_number = fetchAndInsertRunkeeperSleepActivities(last_updated_url_for_activities, last_updated_headers_for_activities)
    # Field "last_updated" is not present. Thus we will ask for all the activities
    except KeyError:
        sleep_activity_number = fetchAndInsertRunkeeperSleepActivities(url, headers)


    social = user.social_auth.get(provider='runkeeper')
    social.extra_data['last_updated'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    social.save()

    if (not runkeeper_activity_id_list) and  sleep_activity_number == 0:
        return HttpResponseBadRequest('Runkeeper Activities are already up to date')
    else:
        return HttpResponse('Runkeeper Activities have been synced')


def syncTwitterActivities(user):
    social_auth_instance = user.social_auth.get(provider='twitter')
    twitter_user_id = social_auth_instance.extra_data['id']
    try:
        api = tweetpony.API(consumer_key=SOCIAL_AUTH_TWITTER_KEY,
                            consumer_secret=SOCIAL_AUTH_TWITTER_SECRET,
                            access_token_secret=str(social_auth_instance.extra_data['access_token']['oauth_token_secret']),
                            access_token=str(social_auth_instance.extra_data['access_token']['oauth_token'])
        )
    except APIError:
        return HttpResponse('Too many requests. Please try again in a few minutes')

    while True:
        try:
            # I am breaking the Calls so that im only asking for old OR new tweets. If i asked for both i would waste
            # the 15 calls/15 minutes that twitter provides me. This way i can get more data inside the 15min window

            since_id = social_auth_instance.extra_data['since_id']
            max_id = social_auth_instance.extra_data['max_id']
            read_all_past_tweets = social_auth_instance.extra_data['read_all_past_tweets']

            # If i haven't read all the past tweets i'll ask only for old tweets until i get them all
            if not read_all_past_tweets:
                tweets= api.user_timeline(user_id=twitter_user_id, count=200, trim_user=True, include_rts=True,
                                       exclude_replies=True, max_id=max_id, contributor_details=True)
                if not tweets:
                    read_all_past_tweets = social_auth_instance.extra_data['read_all_past_tweets'] = True

            # If i have finished with the old, i can ask only for new tweets that happen after the last sync
            if read_all_past_tweets:
                tweets = api.user_timeline(user_id=twitter_user_id, count=200, trim_user=True, include_rts=True,
                                       exclude_replies=True, since_id=since_id, contributor_details=True)

        # Exception happens if i haven't synced before
        except KeyError:
            tweets = api.user_timeline(user_id=twitter_user_id, count=200, trim_user=False, include_rts=True,
                                       exclude_replies=True, contributor_details=True)
            max_id = since_id = 0
            social_auth_instance.extra_data['read_all_past_tweets'] = False

        # If set is Empty i'm done syncing
        if not tweets:
            social_auth_instance.save()
            break

        # If max API Calls for the time window is reached, tweets variable will contain a field 'errors'
        try:
            tweets[0]['errors']
            return HttpResponseBadRequest('Request Limit Reached. Please Re-Sync in a few minutes time')
        except:
            pass


        for tweet in tweets:

            # Get type of tweet, simple or retweet and choose the proper "result" text
            if tweet.retweeted:
                activity_performed = Activity.objects.get(activity_name="Share / Retweet")
                result = "Including yours, there is a total of " + str(tweet.retweet_count) + " retweets at the moment."
                if tweet.favorited:
                    result = "You have favorited this tweet. " + result
            else:
                activity_performed = Activity.objects.get(activity_name="Status Update")
                result = "Your tweet has been retweeted " + str(tweet.retweet_count) + " and favorited " + \
                         str(tweet.favorite_count) + " times at the moment"

            # Check if the user has picked the "Exact Location" Option
            if tweet.coordinates is not None:
                location_lat = tweet.coordinates['coordinates'][1]
                location_lng = tweet.coordinates['coordinates'][0]
                location_address = str(Geocoder.reverse_geocode(location_lat, location_lng)[0])
            # Else if check if the user has chosen the simple "Location" Option
            elif tweet.place is not None:
                location_lat = (tweet.place['bounding_box']['coordinates'][0][0][1] \
                               + tweet.place['bounding_box']['coordinates'][0][2][1]) /2.0
                location_lng = (tweet.place['bounding_box']['coordinates'][0][0][0] \
                               + tweet.place['bounding_box']['coordinates'][0][1][0]) /2.0
                location_address = tweet.place['full_name']
            # Else, if there was no Location added
            else:
                location_lat = None
                location_lng = None
                location_address = ""

            # The medium used for the status update. Here is Twitter but elsewhere could be others i.e. Facebook
            object_used = "Twitter"

            # We cant access the Goal of the user from Twitter
            goal = ""
            goal_status = None

            # The starting time of the tweet is standardized as 1 min before the tweet was posted
            start_date = datetime.strptime(str(tweet.created_at), "%Y-%m-%d %H:%M:%S") - timedelta(seconds=60)
            end_date = datetime.strptime(str(tweet.created_at), "%Y-%m-%d %H:%M:%S")

            # The physical entities that participated in the tweet
            friends = ','.join([user_mention['name'] for user_mention in tweet.entities['user_mentions']])

            # Add the activity to the database
            performs_instance = addActivityFromProvider(user=user, activity=activity_performed, friends=friends,
                                    goal=goal, goal_status=goal_status, location_address=location_address,
                                    location_lat=location_lat, location_lng=location_lng, start_date=start_date,
                                    end_date=end_date, result=result, objects=object_used)

            # Update max_id (will help to get tweets older than the id of this tweet) for optimization of results
            if (tweet.id < max_id) or (max_id == 0):
                max_id = tweet.id

            # Update since_id (will help to get tweets more recent than this tweet) for optimization of results
            if (tweet.id > since_id) or (since_id == 0):
                since_id = tweet.id

            # Store the activity "linking" in our database
            tweet_url = "https://twitter.com/statuses/" + tweet.id_str
            createActivityLinks('twitter', performs_instance, str(tweet.id), tweet_url)

        # reduce by 1 so we don't fetch the same tweet again
        if max_id != 0:
            max_id -= 1

        # Store user variables inside the database
        social_auth_instance.extra_data['max_id'] = max_id
        social_auth_instance.extra_data['since_id'] = since_id

        # Save everything
        social_auth_instance.save()

    return HttpResponse("Twitter Activities have been synced")


def verifyRunkeeperAccess(social_auth_instance):
    if requests.get(
        url='http://api.runkeeper.com/user',
        headers= {
            'Host': 'api.runkeeper.com',
            'Authorization': 'Bearer '+ str(social_auth_instance.extra_data['access_token']),
            'Accept': 'application/vnd.com.runkeeper.User+json'
        }
    ).status_code == 200:
        return 'Authentication Successful'
    else:
        return 'Authentication Failed'

def verifyTwitterAccess(social_auth_instance):
    try:
        api = tweetpony.API(consumer_key=SOCIAL_AUTH_TWITTER_KEY,
                        consumer_secret=SOCIAL_AUTH_TWITTER_SECRET,
                        access_token_secret=str(social_auth_instance.extra_data['access_token']['oauth_token_secret']),
                        access_token=str(social_auth_instance.extra_data['access_token']['oauth_token'])
        )
        return 'Authentication Successful'
    except APIError as error:
        if error.code == 88:
            return "Cannot Process Request"
        else:
            return 'Authentication Failed'


def checkConnection(user, provider):
    try:
        social_auth_instance = user.social_auth.get(provider=provider)
        return  providerAuthenticationFunctions[provider](social_auth_instance)
    except ObjectDoesNotExist:
        return 'Not Connected'


def getAppManagementDomValues(status, provider):
    if status == "Not Connected":
        return {     'buttonText': 'Connect App',
                     'buttonClassColor': 'blueNavy',
                     'statusText': 'App not Connected',
                     'statusIcon': 'icon-remove-circle',
                     'statusFontColor': 'red',
                     'providerIconName': provider
        }
    elif status == "Authentication Failed":
        return {     'buttonText': 'Re-authorize',
                     'buttonClassColor': 'orange',
                     'statusText': 'App manually de-authorized',
                     'statusIcon': 'icon-warning-sign',
                     'statusFontColor': 'orange',
                     'providerIconName': provider
        }
    elif status == "Cannot Process Request":
        return {     'buttonText': 'Try again',
                     'buttonClassColor': 'grey',
                     'statusText': 'Too many requests sent. Try again later',
                     'statusIcon': 'icon-warning-sign',
                     'statusFontColor': 'red',
                     'providerIconName': provider
        }
    else:
        return {     'buttonText': 'Disconnect',
                     'buttonClassColor': 'red',
                     'statusText': 'App connected',
                     'statusIcon': 'icon-ok-circle',
                     'statusFontColor': 'green',
                     'providerIconName': provider
        }


# only providers that cant supply our app with activity data. Not providers for simply logging in
available_providers = ['twitter', 'runkeeper', 'instagram']
providerSyncFunctions = {
        'runkeeper': syncRunkeeperActivities,
        'twitter': syncTwitterActivities,
        #'instagram': syncInstagramActivities,
        #'facebook': syncFacebookActivities,
        #'google': syncGoogleActivities
    }

providerAuthenticationFunctions = {
    'runkeeper': verifyRunkeeperAccess,
    'twitter': verifyTwitterAccess,
    #'instagram': verifyInstagramAccess
}