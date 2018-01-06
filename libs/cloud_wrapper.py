import logging.config
import os

from api_config import log_config
from libs.aws_interface import AWSInterface
from libs.db_wrapper import DataStore

logging.config.dictConfig(log_config)
logger = logging.getLogger("cloud_wrapper")


class CloudWrapper:

    def __init__(self, cloud_provider):
        self.cloud_provider = cloud_provider
        logger.debug("The System timezone was setted up to {}".format(os.getenv('TZ')))

    def getInstancePrice(self, instanceID, instanceLocation=None):

        price = None
        if 'aws' in self.cloud_provider:
            aws = AWSInterface()
            price = aws.get_ec2_price(instanceID, instanceLocation)
        return price

    def getInstanceDetails(self, instanceID, instanceLocation=None):
        details = None
        if 'aws' in self.cloud_provider:
            aws = AWSInterface()
            details = aws.get_instance_details(instanceID, instanceLocation)
        return details

    def getSimpleInstanceList(self, state='all', tag_key=None, tag_value=None):
        instances_list = None
        if 'aws' in self.cloud_provider:
            aws = AWSInterface()
            instances_list = aws.get_simple_instances_list(state, tag_key, tag_value)
        return instances_list

    def make_low_utilization(self, tag_key=None, tag_value=None, max_cpu=None, max_mem_available=None, network=None,
                             test_mode=False):
        low_utilizations = None
        ds = DataStore()
        db = "cloud_mon"
        table = None
        if 'aws' in self.cloud_provider:
            table = "aws_low_utilization"
            aws = AWSInterface(test_mode)
            low_utilizations = aws.get_low_utilization_instances(tag_key=tag_key, tag_value=tag_value, max_cpu=max_cpu,
                                                                 max_mem_available=max_mem_available, network=network)

            ds.save(db, table, low_utilizations)
        if 'googlecloud' in self.cloud_provider:
            low_utilizations = None
            ds.save('gc_low_utilization', low_utilizations)
            pass
        return low_utilizations

    def get_low_utilization_real_time(self, instance_id=None, instance_region=None, tag_key=None, tag_value=None,
                                      max_cpu=None,
                                      max_mem_available=None, network=None):
        low_utilizations = None
        if 'aws' in self.cloud_provider:
            aws = AWSInterface()
            low_utilizations = aws.get_low_utilization_instances(instance_id, instance_region, tag_key, tag_value,
                                                                 max_cpu, max_mem_available, network)
            return low_utilizations

    def get_low_utilization_from_db(self, instance_id=None, instance_region=None, tag_key=None, tag_value=None):
        ds = DataStore()
        db = "cloud_mon"
        table = "aws_low_utilization"
        low_utilizations = ds.get_low_utilization_db(db, table, instance_id, instance_region, tag_key, tag_value)
        return low_utilizations
