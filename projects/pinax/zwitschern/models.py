from datetime import datetime

from django.db import models
from django.utils.html import escape

from django.contrib.auth.models import User

# relational databases are a terrible way to do
# multicast messages (just ask Twitter) but here you have it :-)

import re
ref_re = re.compile("@(\w+)")

def make_link(text):
    username = text.group(1)
    return """@<a href="/profiles/%s/">%s</a>""" % (username, username)

def format_tweet(text):
    return ref_re.sub(make_link, escape(text))
    
class Tweet(models.Model):
    """
    a single tweet from a user
    """
    
    text = models.CharField(max_length=140)
    sender = models.ForeignKey(User, related_name="sent_tweets")
    sent = models.DateTimeField()
    
    def html(self):
        return format_tweet(self.text)
    
    class Meta:
        ordering = ('-sent', )
    
    class Admin:
        list_display = ('id', 'sender', 'text',)

class TweetInstance(models.Model):
    """
    the appearance of a tweet in a follower's timeline
    
    denormalized for better performance
    """
    
    text = models.CharField(max_length=140)
    sender = models.ForeignKey(User, related_name="sent_tweet_instances")
    recipient = models.ForeignKey(User, related_name="received_tweet_instances")
    sent = models.DateTimeField()
    
    def html(self):
        return format_tweet(self.text)
    
    class Admin:
        list_display = ('id', 'sender', 'text', 'recipient',)

def tweet(user, text):
    now = datetime.now()
    Tweet(text=text, sender=user, sent=now).save()
    for follower in (following.follower for following in user.followers.all()):
        TweetInstance(text=text, sender=user, recipient=follower, sent=now).save()
    # add sender
    TweetInstance(text=text, sender=user, recipient=user, sent=now).save()
    # @@@ doesn't also send to non-following @recipients yet


class FollowingManager(models.Manager):
    
    def is_following(self, follower, followed):
        try:
            following = self.get(follower=follower, followed=followed)
            return True
        except Following.DoesNotExist:
            return False
    
    def follow(self, follower, followed):
        if follower != followed and not self.is_following(follower, followed):
            Following(follower=follower, followed=followed).save()
    
    def unfollow(self, follower, followed):
        try:
            following = self.get(follower=follower, followed=followed)
            following.delete()
        except Following.DoesNotExist:
            pass    


class Following(models.Model):
    
    follower = models.ForeignKey(User, related_name="followed")
    followed = models.ForeignKey(User, related_name="followers")
    
    objects = FollowingManager()
    
    class Admin:
        list_display = ('id', 'follower', 'followed',)

