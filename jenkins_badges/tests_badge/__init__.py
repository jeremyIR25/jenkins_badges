from flask import send_file, Blueprint, current_app
import requests
import io
from collections import namedtuple

from six.moves.urllib_parse import urljoin

Tests = namedtuple("Tests", ["status", "colour"])

tests_badge = Blueprint('tests_badge', __name__)


@tests_badge.route("/tests/<path:job_name>/<path:branch_name>", methods=['GET'])
def send_tests_badge(job_name, branch_name):
    if job_name == "favicon.ico":
        return "", 200

    jurl = generate_jenkins_api_url(job_name, branch_name)
    auth = (current_app.config['JENKINS_USERNAME'],
            current_app.config['JENKINS_TOKEN'])
    auth = None if auth == (None, None) else auth
    jresp = requests.get(jurl, auth=auth)
    print("GET {} {}".format(jresp.status_code, jurl))
    if jresp.status_code != 200:
        return send_error_badge()

    tests = extract_tests_number(jresp)
    surl = generate_shields_url(tests)
    sresp = requests.get(surl, stream=True)
    print("GET {} {}".format(sresp.status_code, surl))
    if sresp.status_code != 200:
        return send_error_badge()

    path = io.BytesIO(sresp.content)
    print("SENDING coverage badge of {}".format(tests.status))
    return send_file(path, mimetype="image/svg+xml", cache_timeout=30), 200


def send_error_badge():
    path = "tests_badge/static/error_badge.svg"
    print("SENDING access fail badge")
    return send_file(path, mimetype="image/svg+xml", cache_timeout=30), 200


def generate_jenkins_api_url(job_name, branch_name):
    api_endpoint = ("job/{0}/job/{1}/lastBuild/api/json"
           "").format(job_name, branch_name)

    return urljoin(current_app.config["JENKINS_BASE_URL"] + "/", api_endpoint)


def extract_tests_number(jresp):
    tests_dict = jresp.json()
    status = get_build_status(tests_dict['result'])
    colour = get_colour(status)
    return Tests(status=status, colour=colour)


def get_build_status(result):
    if result == "FAILURE":
        return "failure"
    elif result == "SUCCESS":
        return "passing"
    elif result == "UNSTABLE":
        return "unstable"
    else:
        return "unknown"

def generate_shields_url(c):
    return ("https://img.shields.io/badge/tests-{0}-{1}.svg".format(c.status, c.colour))


def get_colour(status):
    if status == "failure":
        return "red"
    elif status == "unstable":
        return "yellow"
    elif status == "success":
        return "brightgreen"
    else:
        return "lightgrey"
