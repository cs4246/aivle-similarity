import glob
import os
import zipfile
import difflib
import time
import logging
import requests
import editdistance
import pickle

import settings
from api import API

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")

# ---

def save_cache(cache):
    logger.info('Saving cache...')
    with open('cache.pickle', 'wb') as handle:
        pickle.dump(cache, handle, protocol=pickle.HIGHEST_PROTOCOL)

def load_cache():
    try:
        logger.info('Loading cache...')
        with open('cache.pickle', 'rb') as handle:
            return pickle.load(handle)
    except:
        logger.info('Load failed. New cache initialized.')
        return {}

# ---

class Similarity(object):
    def __init__(self, submission, target, score, diff):
        self.submission = submission
        self.target = target
        self.score = score
        self.diff = diff

    def json(self):
        return {
            'task_id': self.submission['task'],
            'user_id': self.submission['user'],
            'submission_id': self.submission['id'],
            'related_id': self.target['id'],
            'score': self.score,
            'diff': self.diff,
        }

# ---

def get_agent_filepath(agent_id):
    return os.path.join(settings.AGENTS_PATH, f"{agent_id}.zip")

def get_template_filepath(task_id):
    return os.path.join(settings.TEMPLATES_PATH, f"{task_id}.zip")

def read_file_in_archive(archive_path, file_path):
    z = zipfile.ZipFile(archive_path, 'r')
    for f in z.namelist():
        if file_path in f:
            return z.read(f)
    raise KeyError

def read_text_in_archive(archive_path, file_path):
    return read_file_in_archive(archive_path, file_path)\
            .decode("utf-8", errors="ignore").replace('\t', '    ')

def extract_content(agent_content, template_content):
    diff = difflib.unified_diff(
                agent_content.splitlines(), 
                template_content.splitlines())
    lines = [l[1:] for l in diff if l[0] == '-']
    return '\n'.join(lines)

# ---

def get_similarity(a, b):
    longer, shorter = a, b
    if len(longer) < len(shorter):
        longer, shorter = b, a
    longer_length = len(longer)
    return (longer_length - editdistance.eval(longer, shorter)) / longer_length;

def get_diff(a, b, fromfile=None, tofile=None):
    diff = difflib.unified_diff(a.splitlines(), b.splitlines(), fromfile=fromfile, tofile=tofile)
    return "\n".join(diff)

# ---

def get_submissions_by_user(task_id):
    api = API(settings.TASK_API)
    response = api.request(id=task_id, action='submissions_by_user')
    return response.json() # { user_id: [ submission ] }

def download(url, path):
    api = API(settings.TASK_API)
    logger.info('Downloading {}...'.format(url))
    response = api.download(url, path)
    if response.status_code != 200:
        raise Exception('Download failed')


class SimilarityClient(object):
    def __init__(self):
        self.api = API(settings.SIMILARITY_API)

    def update(self, data, retry=3, retry_delay=10):
        print(data['task_id'], data['user_id'], data['submission_id'], data['related_id'], round(data['score'], 3))
        response = self.api.request(action='set', method='post', json=data)
        if response.status_code != 200:
            logger.error('Update failed: {}'.format(response))
            if retry > 0:
                time.sleep(retry_delay)
                logger.info('Retrying... [{}]'.format(retry))
                self.update(data, retry-1, retry_delay)
            else:
                logger.info('Max retry reached.')
            return
        logger.info('Update successful.')

    def update_batch(self, similarities):
        for user_id, similarity in similarities.items():
            self.update(similarity.json())

# ---

def get_max_score_submissions(submissions_by_user):
    max_score_submissions = {}
    for user_id, submissions in submissions_by_user.items():
        for submission in submissions:
            if submission['point'] is None:
                submission['point'] = 0.0
            if not isinstance(submission['point'], float):
                submission['point'] = float(submission['point'])
            if user_id not in max_score_submissions:
                max_score_submissions[user_id] = submission
            if submission['point'] > max_score_submissions[user_id]['point']:
                max_score_submissions[user_id] = submission
    return max_score_submissions # { user_id: submission }

def get_similarities(max_score_submissions, content_fn):
    items = list(max_score_submissions.items())
    similarities = {}
    for i, data in enumerate(items):
        user_id, submission = data
        for opponent_id, target in items[i:]:
            if user_id == opponent_id:
                continue

            user_content, fromfile = content_fn(submission)
            opponent_content, tofile = content_fn(target)

            score = get_similarity(user_content, opponent_content)
            diff = get_diff(user_content, opponent_content, fromfile=fromfile, tofile=tofile)

            if user_id not in similarities or score > similarities[user_id].score:
                similarities[user_id] = Similarity(submission, target, score, diff)
            if opponent_id not in similarities or score > similarities[opponent_id].score:
                similarities[opponent_id] = Similarity(target, submission, score, diff)

            # DEBUG
            s = similarities[user_id].json()
            t = similarities[opponent_id].json()
            print(s['task_id'], s['user_id'], s['submission_id'], s['related_id'], round(s['score'], 3), end="\t<==>\t")
            print(t['task_id'], t['user_id'], t['submission_id'], t['related_id'], round(t['score'], 3))
            # return similarities

    return similarities # { user_id: Similarity }

def get_task_similarities(task):
    submissions_by_user = get_submissions_by_user(task['id'])
    max_score_submissions = get_max_score_submissions(submissions_by_user)

    def content_fn(submission):
        agent_path = get_agent_filepath(submission['id'])
        template_path = get_template_filepath(task['id'])
        agent_content = read_text_in_archive(agent_path, task['template_file'])
        template_content = read_text_in_archive(template_path, task['template_file'])
        return extract_content(agent_content, template_content), \
                os.path.join(str(submission['id']), task['template_file'])

    similarities = get_similarities(max_score_submissions, content_fn)
    return similarities

# ---

def handler(client, data, cache=None):
    for task in data['results']:
        # if task['id'] != 4: # DEBUG
        #     print('SKIP:', task['id'])
        #     continue

        if task['template_file'] is None:
            continue

        submissions_by_user = get_submissions_by_user(task['id'])
        if cache.get(task['id']) == submissions_by_user:
            logger.info('Submissions for task {} unchanged. Skipping.'.format(task['id']))
            continue
        cache[task['id']] = submissions_by_user
        save_cache(cache)

        similarities = get_task_similarities(task)
        client.update_batch(similarities)

def monitor(client, cache=None, sleep=3600):
    api = API(settings.TASK_API)
    more = True
    while True:
        if not more:
            time.sleep(sleep)
        try:
            r = api.request()
            if r.status_code != 200:
                more = False
                logger.error(r.status_code)
                continue
            more = handler(client, r.json(), cache)
        except requests.exceptions.ConnectionError as e:
            logger.info('Can\'t connect to aiVLE')
            more = False

cache = {}
client = SimilarityClient()
monitor(client, cache)