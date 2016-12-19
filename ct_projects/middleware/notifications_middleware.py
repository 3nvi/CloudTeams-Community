class NotificationsMiddleware(object):

    # Inject unread notifications to user
    def process_request(self, request):
        if request.user.is_authenticated():
            # get persistent notifications
            request.user.unread_notifications = list(request.user.notifications.filter(seen=False, persistent=True))

            # mark notifications as seen once user visits notifications page
            if request.path == '/profile/notifications/':
                request.user.notifications.filter(seen=False, persistent=True).update(seen=True)

            # get inline notifications (if not an ajax request)
            if not request.is_ajax():
                qs = request.user.notifications.filter(persistent=False, seen=False)
                notifications = list(qs)
                qs.update(seen=True)
                request.user.inline_notifications = notifications
