
from google.appengine.ext import ndb


class Songs(ndb.Model):
    title = ndb.StringProperty(required=True)
    artist = ndb.StringProperty(required=True)
    year = ndb.StringProperty(required=True)


class Hashes(ndb.Expando):
    song_list = ndb.PickleProperty(repeated=True)


class API_keys(ndb.Model):
    api_key = ndb.StringProperty(required=True)
