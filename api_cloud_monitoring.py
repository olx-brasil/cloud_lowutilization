import logging
import os
from concurrent.futures import ThreadPoolExecutor

from bson.json_util import dumps
from flask import Flask, request, Response, jsonify, make_response, abort

from api_config import log_config, main_config
from libs.cloud_wrapper import CloudWrapper
from libs.tools import convert_anything_to_bool, config_fallback

logging.config.dictConfig(log_config)
logger = logging.getLogger(__name__)

TZ = main_config["system_timezone"]
logger.info("Setting the system timezone to {}".format(TZ))
os.environ['TZ'] = TZ

app = Flask(__name__)
executor = ThreadPoolExecutor(1)

global TEST_MODE
TEST_MODE = convert_anything_to_bool(os.getenv('TEST_MODE'))


def make_low_utilization(tag_key=None, tag_value=None, max_cpu=None, max_availiableemory=None, network=None):
    tag_key = None
    tag_value = None

    if max_cpu is None or max_availiableemory is None or network is None:
        max_cpu = config_fallback(main_config['system_percent_max_cpu'], fallback=50)
        max_mem_available = config_fallback(main_config['system_percent_max_availiablememory'], fallback=50)
        network = config_fallback(main_config['system_network_io_mega'], fallback=150)

    cloud = CloudWrapper('aws')
    status = cloud.make_low_utilization(tag_key=tag_key, tag_value=tag_value, max_cpu=max_cpu,
                                        max_mem_available=max_mem_available, network=network, test_mode=TEST_MODE)
    if status:
        logger.info("make_low_utilization has been finished!")
    else:
        logger.error("make_low_utilization finish with error")


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Notfound'}), 404)


@app.route('/')
def hello_world():
    return make_response(jsonify({'success': 'Cloud Mon API =)'}), 200)


@app.route('/routines/v1.0/lowutilization')
def run_make_low_utilization():
    executor.submit(make_low_utilization)
    return make_response(jsonify({'success': 'Running in Background and saving into DB...'}), 200)


@app.route('/api/v1.0/lowutilization', methods=['GET'])
def run_low_utilization():
    tag_key = request.args.get('tag_key')
    tag_value = request.args.get('tag_value')
    cloud = CloudWrapper('aws')
    obj = cloud.get_low_utilization_from_db(tag_key=tag_key, tag_value=tag_value)
    if obj is None:
        abort(404)
    obj_formatted = dumps(obj)
    response = Response(obj_formatted, status=200, mimetype='application/json')
    return response


if __name__ == '__main__':

    if TEST_MODE is True:
        print("TEST MODE ON")
        make_low_utilization()
    else:
        API_DEBUG = convert_anything_to_bool(config_fallback(main_config['api_flash_debug'], fallback=True))
        LISTINER_IP = str(config_fallback(main_config['api_listner_ip'], fallback="0.0.0.0"))
        LISTINER_PORT = int(config_fallback(main_config['api_listner_port'], fallback=8080))
        app.run(debug=API_DEBUG, host=LISTINER_IP, port=LISTINER_PORT)
