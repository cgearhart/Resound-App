#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import logging
import os
import json

import webapp2
import jinja2

import resound

from collections import defaultdict
from scipy.io import wavfile

from google.appengine.ext import ndb
from google.appengine.ext.ndb import Key, Future

from models import Hashes, Songs


API_ENTITY_KEY = "agxzfnJlc291bmRhcHByFQsSCEFQSV9rZXlzGICAgICAgIAKDA"

MIN_MATCH_THRESHOLD = 20

# JINJA configuration
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
JINJA_ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
                               autoescape=True)


class MainHandler(webapp2.RequestHandler):

    def get(self):
        """ Render the main web app page (including GetUserMedia JS lib) """
        template = JINJA_ENV.get_template('main.html')
        self.response.write(template.render())


class IDHandler(webapp2.RequestHandler):

    def get(self, song_id=None):
        """
        Render the song lookup response page based on the urlsafe id parameter
        """
        template = JINJA_ENV.get_template('song.html')
        params = {}
        logging.info("Get song: {}".format(song_id))

        if not song_id:
            logging.debug("Blank id parameter.")
            params = {"msg": "Sorry! No match found."}
        else:
            song_key = Key(urlsafe=song_id)
            if song_key.id():
                params = {"song": song_key.get()}
                logging.debug("song key: {}\nsong: {}".format(str(song_key),
                                                              params["song"]))
            else:
                params = {"msg": "Invalid song ID."}

        self.response.write(template.render(**params))

    def post(self):
        """
        Find the best matching song id in response to POST requests containing
        a file-like object with valid WAV encoding in the request body by
        correlating hashes and relative offsets from the WAV data with
        previously-computed hash records.
        """
        request_file = self.request.body_file.file
        rate, src_audio = wavfile.read(request_file)
        votes = defaultdict(lambda: 0)

        hashes = list(resound.hashes(src_audio, rate))
        keys = [Key(Hashes, h_id) for h_id, _ in hashes]

        futures = ndb.get_multi_async(keys)
        for (h_id, offset), future in zip(hashes, futures):
            entity = future.get_result()  # wait for response from each key

            if not entity:
                continue

            for song_id, abs_offset in entity.song_list:
                delta = abs_offset - offset
                votes[(song_id, delta)] += 1

        # Find the best match
        max_votes, best_id = 0, None
        p_votes, prev = 0, None
        s_votes, prev_2 = 0, None
        for (song_id, _), vote_count in votes.iteritems():
            if max_votes < vote_count:
                max_votes, p_votes, s_votes = vote_count, max_votes, p_votes
                best_id, prev, prev_2 = song_id, best_id, prev
            elif p_votes < vote_count:
                p_votes, s_votes = vote_count, p_votes
                prev, prev_2 = song_id, prev
            elif s_votes < vote_count:
                s_votes = vote_count
                prev_2 = song_id

        msg = "Best ids:\n1. {} - {}\n2. {} - {}\n3. {} - {}"
        logging.debug(msg.format(best_id, max_votes,
                                 prev, p_votes,
                                 prev_2, s_votes))

        if max_votes > MIN_MATCH_THRESHOLD:
            key = Key(Songs, best_id)
            self.response.write(key.urlsafe())


class SongHandler(webapp2.RequestHandler):

    def post(self):
        """
        Add song records in response to POST requests containing JSON encoded
        data in the request body. Body data must be a list of dicts:
        [{'title': <string>, 'artist': <string>, 'year': <string>}, ...]
        """
        entity = Key(urlsafe=API_ENTITY_KEY).get()
        if self.request.headers['API_KEY'] != entity.api_key:
            self.error(401)
            return
        logging.info("POST - message body:\n {}".format(self.request.body))
        keys = []
        data = json.loads(self.request.body)
        for song in data:
            song_ent = Songs.query(Songs.title == song['title'],
                                   Songs.artist == song['artist'],
                                   Songs.year == song['year']).get()
            if not song_ent:
                new_key = Songs(**song).put()
                keys.append(new_key.id())
            else:
                keys.append(song_ent.key.id())

        self.response.headers.add_header('Content-Type', 'application/json')
        self.response.out.write(json.dumps(keys))


class HashGroupHandler(webapp2.RequestHandler):

    def post(self):
        """
        Add audio fingerprint hash records to the database in response to POST
        requests containing JSON encoded data in the body. Body data should
        be a dict containing the database key id for the song being added and
        a list of tuples containing a hash id and list of absolute offsets
        in the song: {"song_id": <int>, "hashes": [(<int>, [<int>, ...]), ...]}
        """
        entity = Key(urlsafe=API_ENTITY_KEY).get()
        if self.request.headers['API_KEY'] != entity.api_key:
            self.error(401)
            return
        body_data = json.loads(self.request.body)
        song_id_key = body_data["song_id"]
        hashes = body_data["hashes"]
        skey = Key(Songs, song_id_key).id()

        logging.info("POST /hashes - length: {}".format(len(hashes)))

        updates = []
        records = ndb.get_multi_async([Key(Hashes, k) for k, _ in hashes])
        for f, (fp_key, offsets) in zip(records, hashes):
            fp = f.get_result() or Hashes(id=fp_key, song_list=[])
            new_entries = [(skey, o) for o in offsets
                           if (skey, o) not in fp.song_list]

            if new_entries:
                fp.song_list.extend(new_entries)
                updates.append(fp)

        if updates:
            Future.wait_all(ndb.put_multi_async(updates))
            logging.info("Handled {} records.".format(len(updates)))

        self.response.headers.add_header('Content-Type', 'application/json')
        self.response.out.write(json.dumps(len(hashes)))


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/id', IDHandler),
    ('/id/(\S+)?', IDHandler),
    ('/songs', SongHandler),
    ('/hashes', HashGroupHandler)
], debug=False)
