from django.db import models
from activitytracker.models import User
from profile_wizard.lists import BUSINESS_SECTORS, WORK_POSITIONS, INFLUENCES, DEVICES_PLATFORMS
from profile_wizard.multiple_choice_field import MultiSelectField

User.profile = property(lambda u: UserProfile.objects.get_or_create(user=u)[0])


class UserProfile(models.Model):
    """
    Additional information about CloudTeams customer account
    Initially will be filled in using the wizard
    """

    # Link to user in Activity Tracker
    user = models.OneToOneField(User)

    # Avatar
    profile_picture = models.ImageField(upload_to='avatars/', blank=True, null=True, default=None)

    # Generic info
    first_name = models.CharField(max_length=255)
    last_name_initial = models.CharField(max_length=1)
    # -- birthday is in main model
    # -- location is in main model -> asume it to be home location

    # Business info
    business_sector = models.CharField(max_length=127, blank=True, default='', choices=BUSINESS_SECTORS)
    work_position = models.CharField(max_length=127, blank=True, default='', choices=WORK_POSITIONS)
    work_location = models.CharField(max_length=255, blank=True, default='')

    # Influences
    influences = MultiSelectField(max_length=2, blank=True, default='', choices=INFLUENCES)

    # Devices & platforms
    devices_and_platforms = MultiSelectField(max_length=2, blank=True, default='', choices=DEVICES_PLATFORMS)

    def get_display_name(self):
        return '%s %s.' % (self.first_name, self.last_name_initial)


class UserBrandOpinion(models.Model):
    user = models.ForeignKey(User, related_name='brand_opinions')
    brand = models.CharField(max_length=2)
    opinion = models.CharField(max_length=1, choices=BRAND_OPINIONS)
