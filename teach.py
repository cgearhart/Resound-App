#/usr/env/bin python

import argparse
import json
import os
import sys

import numpy as np
import requests

from argparse import ArgumentTypeError
from collections import defaultdict
from itertools import izip_longest

from pydub import AudioSegment

from ResoundApp.scipy.io import wavfile
from ResoundApp import resound


API_KEY = None

# unbuffered write object for status bar printing
UNBUFFERED = os.fdopen(sys.stdout.fileno(), 'w', 0)


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    args = [iter(iterable)] * n
    return izip_longest(fillvalue=fillvalue, *args)


def print_status_bar(percent_complete):
    bar = "[{:<78}]".format("#" * int(78 * percent_complete / 100))
    percentage = "{}%".format(int(percent_complete))
    i = 41 - len(percentage)
    line = ' '.join([bar[:i - 1], percentage, bar[42:]])
    UNBUFFERED.write("\r" + line)


def readable_dir(folder):
    """ Validate type and permissions for directory type in argparse """
    msg = None
    if not os.path.isdir(folder):
        msg = "{} is not a valid directory."
    elif os.access(folder, os.R_OK):
        return folder
    else:
        msg = "You do not have permission to access {}"
    raise ArgumentTypeError(msg.format(folder))


def add_songs(filenames, url):
    """
    Parse the filenames for artist, title, and year parameters and make
    a bulk POST request to the webserver to add them to the database.
    """
    songs = []
    for fn in filenames:
        name, _, ext = fn.rpartition(".")
        # spaces around split char required for hyphenated names, e.g., Ne-Yo
        artist, title, year = name.split(' - ')
        songs.append({"artist": artist, "title": title, "year": year})

    headers = {"API_KEY": API_KEY}
    response = requests.post(url, data=json.dumps(songs), headers=headers)
    song_ids = response.json()

    print "\tCompleted with {} keys.".format(len(song_ids))

    return song_ids


def add_hashes(filename, song_id, url):
    """
    Calculate the fingerprint hashses of the referenced audio file and make
    a bulk POST request to the webserver to add them to the database.
    """
    # open the file & convert to wav
    mp3_data = AudioSegment.from_file(filename, format="mp3")
    mp3_data = mp3_data.set_channels(1)  # convert to mono
    wav_tmp = mp3_data.export(format="wav")  # write to a tmp file buffer
    wav_tmp.seek(0)
    rate, wav_data = wavfile.read(wav_tmp)
    fp_data = list(resound.hashes(np.array(wav_data)))

    if not fp_data:
        return

    # Combine duplicate keys before making database requests
    counter = defaultdict(lambda: [])
    for fp, offset in fp_data:
        counter[fp].append(offset)

    # logger.debug("\tFound {} keys.".format(len(fp_data)))

    hash_groups = grouper(counter.items(), 500)
    completion = 0
    for hg in hash_groups:
        # filter out padding from grouper()
        valid_hashes = [h for h in hg if h]

        data = {"song_id": song_id, "hashes": valid_hashes}
        headers = {"API_KEY": API_KEY}
        response = requests.post(url, data=json.dumps(data), headers=headers)
        if response.status_code != requests.codes.ok:
            print "Error on: {} {}".format(filename, song_id)
            return

        completion += response.json()
        print_status_bar(100 * completion / len(counter))

    print "\n",


parser = argparse.ArgumentParser(description="Send the fingerprint " +
                                 "signature of a music file as an HTTP " +
                                 "POST request to a web server.")
parser.add_argument('folder', type=readable_dir)
parser.add_argument('url')
parser.add_argument('key')
parser.add_argument("-e", "--extension")
parser.add_argument("-s", "--skip", type=int)

if __name__ == "__main__":
    args = parser.parse_args()

    filenames = [f for f in os.listdir(args.folder)
                 if os.path.splitext(f)[1][1:] == args.extension]

    API_KEY = args.key

    print "Requesting song id numbers."
    song_ids = add_songs(filenames, args.url + "/songs")

    print "Processing audio."
    for idx, (filename, song_id) in enumerate(zip(filenames, song_ids)):
        if args.skip and idx < args.skip:
            print "Skipping #{}: {}".format(idx + 1, filename)
            continue

        print "Processing #{}: {}".format(idx + 1, filename)
        add_hashes(os.path.join(args.folder, filename),
                   song_id,
                   args.url + "/hashes")
