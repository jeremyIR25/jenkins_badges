from flask import send_file, Blueprint, current_app
import requests
import io
import json
import os.path
from jsonschema import validate, ValidationError
from collections import namedtuple

from six.moves.urllib_parse import urljoin

Tests = namedtuple("Tests", ["status", "colour", "service", "passed", "totals"])
ServiceResults = namedtuple("ServiceResults", ["result", "passed", "failed", "total"])

tests_badge = Blueprint('tests_badge', __name__)

@tests_badge.route("/tests/<path:job_name>/<path:branch_name>", defaults={'service_name': None}, methods=['GET'])
@tests_badge.route("/tests/<path:job_name>/<path:branch_name>/<path:service_name>", methods=['GET'])
def send_tests_badge(job_name, branch_name, service_name):
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

    tests = extract_tests_number(jresp, service_name)
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


def extract_tests_number(jresp, service_name):
    tests_dict = jresp.json()
    status = get_build_status(tests_dict['result'])
    colour = get_colour(status)

    passed = 0
    totals = 0
    actions = tests_dict['actions']
    for action in actions:
    	if '_class' in action and action['_class'] == 'hudson.model.ParametersAction' and 'parameters' in action:
    		parameters = action['parameters']
    		for param in parameters:
    			if '_class' in param and param['_class'] == 'hudson.model.StringParameterValue' and 'name' in param:
    				if param['name'] == 'NUM_TESTS_SUCCEDED':
    					passed = param['value']
    				elif param['name'] == 'TOT_TESTS':
    					totals = param['value']

    return Tests(status=status, colour=colour, service=service_name, passed=passed, totals=totals)


def get_build_status(result):
    if result == "FAILURE":
        return "failing"
    elif result == "SUCCESS":
        return "passing"
    elif result == "UNSTABLE":
        return "unstable"
    elif result ==  "ABORTED":
        return "aborted"
    elif not result:
        return "running"
    else:
        return "unknown"

def generate_shields_url2(c):
    if c.status == "passing" or c.status == "failure":
        filename = current_app.config["TESTS_RESULTS_FILE_NAME"]
        if filename and os.path.isfile(filename):
            r = read_file_results_stats(filename, c.service)
            if r:
                service_colour = get_test_colour(get_build_status(r.result), r)
                return ("https://img.shields.io/badge/tests-{0}/{1}-{2}.svg".format(r.passed, r.total, service_colour))

    return ("https://img.shields.io/badge/tests-{0}-{1}.svg".format(c.status, c.colour))

def generate_shields_url(c):
    if c.status == "passing" or c.status == "failure" and c.totals != 0:
        service_colour = get_test_colour(get_build_status(c.status), c)
        return ("https://img.shields.io/badge/tests-%20{0}%20/%20{1}%20-{2}.svg".format(c.passed, c.totals, service_colour))

    return ("https://img.shields.io/badge/tests-{0}-{1}.svg".format(c.status, c.colour))

def read_file_results_stats(filename, service_name):
    with open(filename, "r", encoding='utf-8') as json_file:
        json_data = json.load(json_file)
        # if not json_is_valid(json_data):
        #    return None
        for service in json_data['services']:
            if service['name'] == service_name:
                return ServiceResults(result=service['result'], passed=service['passed'], failed=service['failed'], total=service['total'])
        # We are not asking a specific service but the total
        return ServiceResults(result=json_data['result'], passed=json_data['passed'], failed=json_data['failed'], total=json_data['total'])

def get_test_colour(status, result):
    yellow_threshold = current_app.config['TESTS_RESULTS_YELLOW_THRESHOLD']
    red_threshold = current_app.config['TESTS_RESULTS_YELLOW_THRESHOLD']

    test_passed_ratio = round(float(result.passed) / float(result.totals), 2)
    if test_passed_ratio > yellow_threshold:
        return "brightgreen"
    elif test_passed_ratio <= yellow_threshold and test_passed_ratio >= red_threshold:
        return "yellow"
    else:
        return "red"

def get_colour(status):
    if status == "failing":
        return "red"
    elif status == "unstable":
        return "yellow"
    elif status == "passing":
        return "brightgreen"
    elif status == "running":
        return "blue"
    else:
        return "lightgrey"

def json_is_valid(json_data):
    schema = {
        "type": "object",
        "properties": {
            "services": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type" : "string"},
                        "passed": {"type" : "integer"},
                        "failed": {"type" : "integer"},
                        "total": {"type" : "integer"}
                    },
                    "required": [
                        "name",
                        "passed",
                        "failed",
                        "total"
                    ]
                }
            },
            "result": {"type" : "string"},
            "passed": {"type" : "integer"},
            "failed": {"type" : "integer"},
            "total": {"type" : "integer"}
        },
        "required": [
            "result",
            "passed",
            "failed",
            "total"
        ]
    }
    try:
        validate(json_data, schema)
        return True
    except ValidationError:
        return False
