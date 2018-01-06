main_config = {
    "api_listner_ip": "0.0.0.0",
    "api_listner_port": "8080",
    "api_flash_debug": True,

    "system_pidfile": "cloud_monitoring.pid",
    "system_percent_max_cpu": 50,
    "system_percent_max_availiablememory": 50,
    "system_network_io_mega": 150,
    "system_timezone": "UTC",
    "system_ssh_timeout": 2,
    "system_ntp_server": "0.north-america.pool.ntp.org, 1.north-america.pool.ntp.org, 2.north-america.pool.ntp.org, 3.north-america.pool.ntp.org",
    "system_loglevel": "DEBUG",
    "system_logfile": None,
    "system_test_mode_ids": [
        {'id': 'i-0aeb5dcc19892e8a6', 'region': 'us-east-1'},
        {'id': 'i-0349b84be2af801c4', 'region': 'sa-east-1'},
        {'id': 'i-07e942ad6c0796443', 'region': 'sa-east-1'},
        {'id': 'i-02c0532f015927db4', 'region': 'sa-east-1'},
        {'id': 'i-075212272e7a51ab9', 'region': 'sa-east-1'},
        {'id': 'i-028103819d9998954', 'region': 'sa-east-1'},
        {'id': 'i-0e44316a6217e7d58', 'region': 'sa-east-1'},
        {'id': 'i-07e5c2f095f72af6e', 'region': 'sa-east-1'},
        {'id': 'i-0349b84be2af801c4', 'region': 'sa-east-1'}
    ],
    "system_test_picke_file": "/Volumes/DataDisk/csmaniotto/projects/cloud_monitoring/df_test.pkl",

    # "aws_regions": ['us-east-1','us-west-1','us-west-2','eu-west-1','sa-east-1', 'ap-southeast-1','ap-southeast-2','ap-northeast-1'],
    "aws_regions": ['sa-east-1'],
    "aws_ssh_key_folder": "/Volumes/DataDisk/csmaniotto/projects/pemkeys/",
    "aws_tag_exclude": ['elasticbeanstalk:', 'aws:', 'k8s.'],

    "mongo-server": "localhost:32768",
    "mongo_db-": "clound_mon",
    "mongo_collection": "low_utilization"
}

log_config = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - [%(levelname)s] %(name)s [%(module)s.%(funcName)s:%(lineno)d]: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'info': {
            'format': '%(levelname)s:%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'debug': {
            'format': '%(asctime)s %(filename)-18s %(levelname)-8s: [ %(funcName)s():%(lineno)s]:  %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        }
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'debug',
        }
    },
    'loggers': {
        '__main__': {  # logging from this module will be logged in VERBOSE level
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': False,
        },

        'aws_interface': {  # logging from this module will be logged in VERBOSE level
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': False,
        },

        'tools': {  # logging from this module will be logged in VERBOSE level
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['default']
    },

}
