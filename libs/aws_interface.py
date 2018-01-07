import json
import logging
import logging.config
from datetime import datetime
from datetime import timedelta

import boto3
import pandas as pd

from api_config import log_config, main_config
from libs.tools import datetime_iso8601, convert_dict_dataframe, ssh_os_linux_available_memory, \
    check_is_file_exist, df_to_picke, picke_to_dataframe, nan2floatzero, check_string_in_list, config_fallback, \
    count_tags, convert_anything_to_bool

# import datetime

logging.config.dictConfig(log_config)
logger = logging.getLogger("aws_interface")


class AWSInterface(object):
    """
        AWSInterface class.
        Methods to get information and reports overs AWS.
    """

    # custom_logger = Logger()
    # logger = log

    aws_connection = None
    ec2_connection = None
    asg_connection = None

    aws_regions = None
    aws_regions = None

    def __init__(self, test_mode=False):
        self.test_mode = test_mode
        logger.warning('AWS INTERFACE INITIALIZED')
        self.aws_regions = main_config["aws_regions"]
        self.aws_connection = None
        try:
            self.aws_connection = boto3.Session()
            logger.debug("AWS Session has been created with success...")
        except Exception as e:
            logger.error("Error to access AWS API {}".format(e))

    def __check_instance_in_asg(self, instance_id, instance_region):
        try:
            asg_connection = self.aws_connection.client('autoscaling', region_name=instance_region)
            instances = asg_connection.describe_auto_scaling_instances(InstanceIds=[instance_id])
            instance_status = instances['AutoScalingInstances']
            if instance_status:
                asgname = instances['AutoScalingInstances'][0]['AutoScalingGroupName']
                logger.debug(
                    "Instance %s is in autoscale group {}".format(instance_id,
                                                                  instance_status[0]['AutoScalingGroupName']))
                return True, asgname
            return False, None
        except Exception:
            logger.error("Error on get ASG information")

    def __aws_region_convert(self, instance_region):

        try:
            regions = {
                "us-east-1": "US East (N. Virginia)",
                "us-east-2": "US East (Ohio)",
                "us-west-1": "US West (N. California)",
                "us-west-2": "US West (Oregon)",
                "sa-east-1": "South America (Sao Paulo)",
                "ca-central-1": "Canada (Central)",
                "ap-northeast-2": "Asia Pacific (Seoul)",
                "ap-south-1": "Asia Pacific (Mumbai)",
                "ca-central-1": "Canada (Central)",
                "eu-central-1": "EU (Frankfurt)",
                "ap-southeast-2": "Asia Pacific (Sydney)",
                "eu-west-1": "EU (Ireland)",
                "ap-southeast-1": "Asia Pacific (Singapore)",
                "ap-northeast-1": "Asia Pacific (Tokyo)",
                "eu-west-2": "EU (London)"
            }
            full_name = regions[instance_region]
            return full_name
        except Exception:
            logger.exception(msg="error on get region full name", exc_info=True)
            exit(1)

    def __avg_cloudwatch_metrics(self, clouldwatchstats):
        try:
            average = 0
            datapoints = clouldwatchstats['Datapoints']
            if len(datapoints) > 0:
                sum = 0
                for n in datapoints:
                    sum = sum + n['Average']
                average = sum / len(datapoints)
                return average
            else:
                return 0
        except Exception as e:
            logger.debug("Error function parseavarage {}".format(e))

    def __cloudwatch_ec2(self, instance_id, aws_region, metricname, starttime, endtime, period):
        try:
            cloudwatch_connection = self.aws_connection.client('cloudwatch', region_name=aws_region)
            query = {
                "Namespace": "AWS/EC2",
                "MetricName": metricname,
                "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                "StartTime": starttime,
                "EndTime": endtime,
                "Period": period,
                "Statistics": ['Average']
            }
            result = cloudwatch_connection.get_metric_statistics(**query)
            return result
        except Exception:
            logger.exception("Error on __cloudwatch_ec2", exc_info=True)

    def __reserved_instances(self, instance_region, instance_type=None, availability_zone=None, state='active'):
        reserved = {}
        try:
            reserved_connection = self.aws_connection.client('ec2', region_name=instance_region)
            if instance_type is None:
                rs = reserved_connection.describe_reserved_instances()
                return reserved

            else:
                rs = reserved_connection.describe_reserved_instances(Filters=[
                    {'Name': 'instance-type',
                     'Values': [instance_type]
                     },
                    # {'Name': 'availability-zone',
                    #  'Values': [availability_zone]
                    # },
                    {'Name': 'state',
                     'Values': [state]
                     }])

                if 'ReservedInstances' in rs.keys():
                    if len(rs['ReservedInstances']) > 0:
                        reserved['scope'] = rs['ReservedInstances'][0]['Scope']
                        reserved['reservedprice'] = rs['ReservedInstances'][0]['UsagePrice']
                        reserved['offeringclass'] = rs['ReservedInstances'][0]['OfferingClass']
                        if 'Region' in rs['ReservedInstances'][0]['Scope']:
                            reserved['availabilityzone'] = instance_region
                        else:
                            reserved['availabilityzone'] = rs['ReservedInstances'][0]['AvailabilityZone']
                        reserved['reservedinstancesid'] = rs['ReservedInstances'][0]['ReservedInstancesId']
                return reserved
        except Exception as e:
            logger.error("Error on get reserved information: {}".format(e))

    def __get_instance_ssh_memory_info(self, instance_ip, instance_ssh_key, instance_id, instance_region):
        # Try to get in the instance, the memory available.
        dict_mem_info = dict()
        dict_mem_info['memtotal'] = -1
        dict_mem_info['memavailable'] = -1
        dict_mem_info['percent_free'] = -1
        dict_mem_info['kernel'] = 'unknown'
        dict_mem_info['distro'] = 'unknown'
        try:
            logger.debug("Try to get in the instance, the memory available.")
            if instance_ip and instance_ssh_key:
                dict_mem_info = ssh_os_linux_available_memory(instance_ip, instance_ssh_key)
                if dict_mem_info['percent_free'] > 0:
                    logger.info("Memory available metric has been captured with success on {}:{}".format(instance_id,
                                                                                                         instance_region))
        except Exception as e:
            logger.exception(
                "It was not possible to collect the memory information of instance {}-{} - {}".format(instance_id,
                                                                                                      instance_region,
                                                                                                      e), exc_info=True)
        finally:
            return dict_mem_info

    def __get_instance_report_agg(self, instance_id, instance_region, aggregation_type='days', aggregation=14,
                                  period=3600):

        if 'days' in aggregation_type:
            starttime = datetime.today() - timedelta(days=int(aggregation))
        if 'minutes' in aggregation_type:
            starttime = datetime.today() - timedelta(minutes=int(aggregation))

        endtime = datetime.today()

        cpu = round(self.__avg_cloudwatch_metrics(
            self.__cloudwatch_ec2(instance_id, instance_region, 'CPUUtilization', starttime, endtime, period)), 2)
        diskr = round(self.__avg_cloudwatch_metrics(
            self.__cloudwatch_ec2(instance_id, instance_region, 'DiskReadOps', starttime, endtime, period)), 2)
        diskw = round(self.__avg_cloudwatch_metrics(
            self.__cloudwatch_ec2(instance_id, instance_region, 'DiskWriteOps', starttime, endtime, period)), 2)
        netin = round(self.__avg_cloudwatch_metrics(
            self.__cloudwatch_ec2(instance_id, instance_region, 'NetworkIn', starttime, endtime, period)), 2)
        netou = round(self.__avg_cloudwatch_metrics(
            self.__cloudwatch_ec2(instance_id, instance_region, 'NetworkOut', starttime, endtime, period)), 2)

        # Get more details from instance-id: SSHKEY, TAGS, IP AND OTHERS.
        details = self.get_instance_details(instance_id, instance_region)

        # Get memory info thougth SSH
        instance_ip = details['instanceIP']
        instance_ssh_key = details['SSHKey']
        dict_mem_info = self.__get_instance_ssh_memory_info(instance_ip, instance_ssh_key, instance_id,
                                                            instance_region, )

        aggr_info = {"InstanceId": instance_id,
                     "InstanceRegion": instance_region,
                     "CPU": cpu,
                     "TotalMemoryBytes": dict_mem_info['memtotal'],
                     "AvailiableMemoryBytes": dict_mem_info['memavailable'],
                     "AvailiableMemoryPerc": dict_mem_info['percent_free'],
                     "kernel": dict_mem_info['kernel'],
                     "distro": dict_mem_info['distro'],
                     "DiskRead": diskr,
                     "DiskWrite": diskw,
                     "NetworkIOBytes_aggr": netin + netou,
                     "NetworkInBytes_aggr": netin,
                     "NetworkOutBytes_aggr": netou,
                     "NetworkInBytesSec": int(netin / period),
                     "NetworkOutBytesSec": int(netou / period),
                     "AggregationType": aggregation_type,
                     "Aggregation_time": aggregation,
                     "Aggregation_period": period
                     }

        try:
            # Concat the Aggr_info + details into a new single dict.
            aggr_info.update(details)
            return aggr_info
        except Exception as e:
            logger.exception("Error in creating aggregation info to instance {} - {}".format(instance_id),
                             exc_info=True)
            pass

    """
    When we call get_low_utilization_instances() all methods (private and public) is used to compose them. 
    However, you can use individually the others public methods to get specific information
    """

    def get_ec2_price(self, instance_type, instance_region):
        try:
            #  By the doc, I need to force Virginia as region to do it works.
            #  http://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-pelong.html
            price_connection = self.aws_connection.client('pricing', region_name='us-east-1')
            region_full_name = self.__aws_region_convert(instance_region)
            rs = price_connection.get_products(ServiceCode='AmazonEC2',
                                               Filters=[
                                                   {'Type': 'TERM_MATCH',
                                                    'Field': "instanceType",
                                                    'Value': instance_type
                                                    },

                                                   {'Type': 'TERM_MATCH',
                                                    'Field': "tenancy",
                                                    'Value': "Shared"
                                                    },

                                                   {'Type': 'TERM_MATCH',
                                                    'Field': "servicename",
                                                    'Value': "Amazon Elastic Compute Cloud"
                                                    },

                                                   {'Type': 'TERM_MATCH',
                                                    'Field': "operatingSystem",
                                                    'Value': "Linux"
                                                    },

                                                   {'Type': 'TERM_MATCH',
                                                    'Field': "location",
                                                    'Value': region_full_name
                                                    }
                                               ]
                                               )
        except Exception as e:
            logger.error("error to get result price with price api {}".format(e))
        price_list = rs['PriceList'][0]
        json_items = json.loads(price_list)
        sku = str(json_items['product']['sku'])  # Stock Keeping Unit (SKU)

        '''
        'JRTCKXETXF' - OnDemand offerTermCode
        '''
        key_ondemand = "{}.JRTCKXETXF".format(sku)
        priced_odidx = str(list(json_items['terms']['OnDemand'][key_ondemand]['priceDimensions'].keys())[0])
        unit_ondemand = json_items['terms']['OnDemand'][key_ondemand]['priceDimensions'][priced_odidx]['unit']
        price_ondemand = json_items['terms']['OnDemand'][key_ondemand]['priceDimensions'][priced_odidx]['pricePerUnit'][
            'USD']

        '''
        RESERVED OFFER TERM CODE
        'BPH4J8HBKS' - {'LeaseContractLength': '3yr', 'OfferingClass': 'standard', 'PurchaseOption': 'No Upfront'}
        'NQ3QZPMQV9' - {'LeaseContractLength': '3yr', 'OfferingClass': 'standard', 'PurchaseOption': 'All Upfront'}
        'HU7G6KETJZ' - {'LeaseContractLength': '1yr', 'OfferingClass': 'standard', 'PurchaseOption': 'Partial Upfront'}
        '6QCMYABX3D' - {'LeaseContractLength': '1yr', 'OfferingClass': 'standard', 'PurchaseOption': 'All Upfront'}
        'R5XV2EPZQZ' - {'LeaseContractLength': '3yr', 'OfferingClass': 'convertible', 'PurchaseOption': 'Partial Upfront'}
        'VJWZNREJX2' - {'LeaseContractLength': '1yr', 'OfferingClass': 'convertible', 'PurchaseOption': 'All Upfront'}
        'MZU6U2429S' - {'LeaseContractLength': '3yr', 'OfferingClass': 'convertible', 'PurchaseOption': 'All Upfront'}
        '38NPMPTW36' - {'LeaseContractLength': '3yr', 'OfferingClass': 'standard', 'PurchaseOption': 'Partial Upfront'}
        '7NE97W5U4E' - {'LeaseContractLength': '1yr', 'OfferingClass': 'convertible', 'PurchaseOption': 'No Upfront'}
        'CUZHX8X6JH' - {'LeaseContractLength': '1yr', 'OfferingClass': 'convertible', 'PurchaseOption': 'Partial Upfront'}
        'Z2E3P23VKM' - {'LeaseContractLength': '3yr', 'OfferingClass': 'convertible', 'PurchaseOption': 'No Upfront'}
        '4NA7Y494T4' - {'LeaseContractLength': '1yr', 'OfferingClass': 'standard', 'PurchaseOption': 'No Upfront'}
        '''
        # Reserved without up front
        keys_reserved = "{}.4NA7Y494T4".format(sku)
        priced_riidx = str(list(json_items['terms']['Reserved'][keys_reserved]['priceDimensions'].keys())[0])
        unit_reserved = json_items['terms']['Reserved'][keys_reserved]['priceDimensions'][priced_riidx]['unit']
        price_reserved = \
            json_items['terms']['Reserved'][keys_reserved]['priceDimensions'][priced_riidx]['pricePerUnit']['USD']

        cost_month_ondemand = 0.00
        cost_month_reserved = 0.00
        percent_difference = 0.00
        save_money = 0.00
        if 'Hrs' in unit_ondemand:
            cost_month_ondemand = float(price_ondemand) * 720
        else:
            cost_month_ondemand = (float(price_ondemand) * 60) * 720

        if 'Hrs' in unit_reserved:
            cost_month_reserved = float(price_reserved) * 720
        else:
            cost_month_reserved = (float(price_reserved) * 60) * 720

        if cost_month_reserved < cost_month_ondemand:
            percent_difference = round(((cost_month_ondemand / cost_month_reserved) - 1) * 100, 2)
            save_money = cost_month_ondemand - cost_month_reserved
        else:
            percent_difference = -1
            save_money = 0.00
            logger.error("Fail to capture reserved price, maybe the value is in quantity instead of hours")

        cost_dict = {'unit_on_demand': unit_ondemand,
                     'price_on_demand': round(float(price_ondemand), 6),
                     'cost_month_ondemand': round(cost_month_ondemand, 6),
                     'unit_reserved': unit_reserved,
                     'price_reserved': round(float(price_reserved), 6),
                     'reserved_offer_term_code': '4NA7Y494T4 - 1yr standard No Upfront',
                     'cost_month_reserved': round(cost_month_reserved, 6),
                     'percent_difference': round(percent_difference, 6),
                     'save_money_month': round(save_money, 2)
                     }
        return cost_dict

    def get_instance_details(self, instance_id, instance_region):
        ec2_connection = self.aws_connection.client('ec2', region_name=instance_region)
        rs = ec2_connection.describe_instances(InstanceIds=[instance_id])
        inasg = None
        asg_name = None
        launchtime = None
        sshkey = None
        private_ip_address = None
        private_dns_name = None
        vpcid = None
        subnetid = None
        tag_name = None
        tag_team = None
        tag_product = None
        tag_owner = None
        tag_env = None
        tag_work = None

        try:
            inasg, asg_name = self.__check_instance_in_asg(instance_id, instance_region)
        except:
            logger.warning(
                "Error on get information about ASG of instance {}:{}".format(instance_id, instance_region))
            pass

        try:
            launchtime = datetime_iso8601((rs['Reservations'][0]['Instances'][0]['LaunchTime']))
        except:
            logger.warning("Error to get launchtime of instance {}:{}", format(instance_id, instance_region))
            pass

        # If inasg = True then not exist KeyName.
        try:
            sshkey = str(rs['Reservations'][0]['Instances'][0]['KeyName'])
        except:
            pass

        imageid = str(rs['Reservations'][0]['Instances'][0]['ImageId'])
        instance_type = str(rs['Reservations'][0]['Instances'][0]['InstanceType'])
        instance_family = str(instance_type.split('.')[0])
        instance_family_generation = instance_family[1:]

        ebs_optimized = convert_anything_to_bool(rs['Reservations'][0]['Instances'][0]['EbsOptimized'])
        state = str(rs['Reservations'][0]['Instances'][0]['State']['Name'])
        state_code = int(rs['Reservations'][0]['Instances'][0]['State']['Code'])

        # state  codes
        # 0(pending), 16(running), 32(shutting - down), 48(terminated), 64(stopping), and 80(stopped).
        if state_code in [16, 64, 80]:
            private_ip_address = rs['Reservations'][0]['Instances'][0]['PrivateIpAddress']
            private_dns_name = rs['Reservations'][0]['Instances'][0]['PrivateDnsName']
            vpcid = rs['Reservations'][0]['Instances'][0]['VpcId']
            subnetid = rs['Reservations'][0]['Instances'][0]['SubnetId']

        availability_zone = str(rs['Reservations'][0]['Instances'][0]['Placement']['AvailabilityZone'])
        ownerid = str(rs['Reservations'][0]['OwnerId'])

        try:
            tags = list(rs['Reservations'][0]['Instances'][0]['Tags'])
            details = {}
            tag_dict = {}
            tags_black_list = main_config['aws_tag_exclude']
            # tags_black_list = ['elasticbeanstalk:', 'aws:', 'k8s.']
            for tag in tags:
                if not check_string_in_list(tag['Key'], tags_black_list):
                    tag_dict.update({'{}'.format(tag['Key']): tag['Value']})
            # details.update({'tags':tag_list})
        except Exception:
            logger.exception("Error on capture tags", exc_info=True)
            pass

        reserved_info = self.__reserved_instances(instance_region, instance_type, availability_zone)
        reservationid = None
        if reserved_info:
            if instance_region == reserved_info['availabilityzone']:
                reservationid = reserved_info['reservedinstancesid']

        details.update({
            "InstanceState": state,
            "SSHKey": sshkey,
            "InASG": inasg,
            "ASGName": asg_name,
            "instance_type": instance_type,
            "instance_family": instance_family,
            "instance_family_generation": instance_family_generation,
            "instance_ebsoptimized": ebs_optimized,
            'instanceIP': private_ip_address,
            "instanceHostName": private_dns_name,
            "instance_vpc_id": vpcid,
            "instance_subnet_id": subnetid,
            "instance_availabilityzone": availability_zone,
            "instance_ami": imageid,
            "instance_account_id": ownerid,
            "instance_reservation_id": reservationid,
            "instance_launch_time": launchtime,
            "instance_tags": tag_dict
        })
        try:
            cost = self.get_ec2_price(instance_type, instance_region)
            details.update(cost)
        except Exception as e:
            logger.error("Error on get instance price".format(e))
            pass

        return details

    def get_simple_instances_list(self, state='all', tag_key=None, tag_value=None):
        """
               Connect into the AWS and get all instance using criteria filter.

               :param str state: 'all' for all state(pending, running, stopped, etc) or individual state
               :param str tag_key: default None, tag name used on the instances
               :param str tag_name: default None, value of tag_key name

               :return:
                   a list with dictionary containts two key: id and region with instance_id  and instance region.

        """
        if "all" in state:
            state = ['pending', 'running', 'shutting-down', 'terminated', 'stopping', 'stopped']
        else:
            state = [state]

        filters = [{'Name': 'instance-state-name',
                    'Values': state}]

        if tag_key is not None and tag_value is not None:
            filters.append({'Name': 'tag:{}'.format(tag_key), 'Values': [tag_value]})

        instance_list = []
        try:
            for region in self.aws_regions:
                logger.info("Getting instances list of regions {}".format(region))
                ec2_connection = self.aws_connection.resource('ec2', region_name=region)
                instances = ec2_connection.instances.filter(Filters=filters)
                for instance in instances:
                    logger.debug("Loading in instance list id:{}  - region: {}".format(instance.id, region))
                    instance_list.append({"id": instance.id, "region": region})
                logger.debug("Finish Loading in instance list...")
            return instance_list
        except Exception:
            logger.exception("Error on get_simple_instances_list", exc_info=True)

    # IF CPU <=50% and NetworkIO <= 500Mb &FreeMemory >= 50%
    def __filter_low_utilization_instances(self, df_all_instances, max_cpu=None, max_mem_available_pct=None,
                                           network_io=None):
        """
        Two phases of filter:
        Phase 1: Get all instances with low use of cpu and low use of NetIO
        Phase 2: Check in list of phase 1 the low use memory to a final list.
        ALL -> criteria cpu+network  -> memory = low inst. list
        """
        # finding the low utilization instances using the criteria...
        # AWS uses as formula to criteria in networkIO in  this way:
        # network_in + network_out <=  x
        network_io_bytes = int(network_io) * (1024 ** 2)
        df_low = df_all_instances[
            (df_all_instances['CPU'] <= max_cpu) & (df_all_instances['NetworkIOBytes_aggr'] <= network_io_bytes)]
        df_low = df_low[
            (df_low['AvailiableMemoryPerc'] < 0) | (df_low['AvailiableMemoryPerc'] >= max_mem_available_pct)]
        return df_low

    def get_low_utilization_instances(self, instance_id=None, instance_region=None, tag_key=None, tag_value=None,
                                      max_cpu=None, max_mem_available_pct=None, network_io=None):

        report = []
        """
               Connect into the AWS and get low utilizations machines.

               :param str tag_key: default None, tag name used on the instances
               :param str tag_name: default None, value of tag_key name


               :return:
                   list with dictionary containts the instances with low utilization with details.

        """
        if self.test_mode is True:
            instances = main_config['system_test_mode_ids']
        elif instance_id is not None and instance_region is not None:
            instances = [{'id': instance_id, 'region': instance_region}]
        else:
            instances = self.get_simple_instances_list(state='running', tag_key=tag_key, tag_value=tag_value)

        df = pd.DataFrame()  # Creating a Pandas DataFrame with the aggregation data per instance.
        instances_processed = 0
        total_instances = len(instances)
        pick_load = False
        pick_file = config_fallback(main_config['system_test_picke_file'], fallback='db_test.pkl')
        if self.test_mode and check_is_file_exist(pick_file):
            df = picke_to_dataframe(pick_file)
            pick_load = True
        else:
            for instance in instances:
                try:
                    instances_processed += 1
                    logger.debug("-----------------------------------------------------------------------------")
                    logger.debug("Starting process to instance-id {}:{}".format(instance['id'], instance['region']))
                    logger.info("Starting process to instance-id {}:{}".format(instance['id'], instance['region']))
                    processed_perc = round((instances_processed * 100 / total_instances), 1)
                    logger.debug(
                        "processed {}% - processing instance {}:{}....".format(processed_perc, instance['id'],
                                                                               instance['region']))
                    aggregation_value = config_fallback(main_config['criteria_aggregation_value'], 14)
                    aggregation_unit = config_fallback(main_config['criteria_aggegation_unit'], 'days')
                    instance_report_dict = self.__get_instance_report_agg(instance_id=instance['id'],
                                                                          instance_region=instance['region'],
                                                                          aggregation_type=aggregation_unit,
                                                                          aggregation=aggregation_value,
                                                                          period=3600)
                    df = pd.concat([df, convert_dict_dataframe(instance_report_dict)])
                    if logging.getLevelName("INFO"):
                        logger.info("Running... Pocessed {}% of ".format(processed_perc, total_instances))
                    else:
                        logger.warning("Running... Pocessed {}% of {}".format(processed_perc, total_instances))

                except (Exception, KeyError, IndexError) as e:
                    logger.critical(
                        "Error {}  to get metrics and saving into the dataframe for instance {} of {}".format(e,
                                                                                                              instance[
                                                                                                                  'id'],
                                                                                                              instance[
                                                                                                                  'region']),
                        exc_info=True)
                    pass

        if self.test_mode and pick_load is False:
            df_to_picke(df, pick_file)

        tags_count = count_tags(df["instance_tags"])
        untagged_owner = tags_count['untagged_owner']
        untagged_team = tags_count['untagged_team']
        untagged_work = tags_count['untagged_work']
        untagged_owner, tags_count['untagged_owner']

        # Finding low utilization...
        # --------------------------
        instances_low_utilizations = 0
        try:

            "Logic of critecis is in the __filter_low_utilization_instances()"
            df_low = self.__filter_low_utilization_instances(df, max_cpu=max_cpu, network_io=network_io,
                                                             max_mem_available_pct=max_mem_available_pct)
            instances_low_utilizations = df_low.shape[0]  # fast way to get number of rows
        except Exception as e:
            logger.exception("Error on summarization low utilization instances{}".format(e), exc_info=True)
            pass

        # Summarization  of instances...
        # ------------------------------
        total_instances = 0
        total_instances_reserved = 0
        total_instances_on_demand = 0
        total_cost_reserved = 0
        total_cost_on_demand = 0
        total_cost_simulated_ri = 0
        total_cost_low_utilization_od = 0
        total_cost_low_utilization_ri = 0

        try:
            total_instances = df.shape[0]
            total_instances_reserved = sum(df["instance_reservation_id"].notnull())
            total_instances_on_demand = sum(df["instance_reservation_id"].isnull())

            # Cost Info...
            total_cost_reserved = nan2floatzero(
                df[df["instance_reservation_id"].notnull()]['cost_month_reserved'].sum())
            total_cost_on_demand = nan2floatzero(
                df[df["instance_reservation_id"].isnull()]['cost_month_ondemand'].sum())

            total_cost_low_utilization_ri = nan2floatzero(
                df_low[df_low["instance_reservation_id"].notnull()]['cost_month_reserved'].sum())
            total_cost_low_utilization_od = nan2floatzero(
                df_low[df_low["instance_reservation_id"].isnull()]['cost_month_ondemand'].sum())


            # Save Money Info
            total_cost_simulated_ri = nan2floatzero(
                df[df["instance_reservation_id"].isnull()]['cost_month_reserved'].sum())
            ri_potential_save = nan2floatzero(df[df["instance_reservation_id"].isnull()]['save_money_month'].sum())
        except Exception as e:
            logger.error("Error on summarization cost information... - {}".format(e))
            pass

        # Creating the JSON Report...
        # ---------------------------
        try:
            now = datetime_iso8601(datetime.today())
            report = {
                "report_date": now,
                "aggregation_details": {
                    "total_examined": total_instances,  # "amount_instances_examined": 421,
                    "total_low_utilization": instances_low_utilizations,
                    "criteria": "cpu <= {}% & mem free >= {}% & netio_aggr <= {}Mb".format(max_cpu,
                                                                                           max_mem_available_pct,
                                                                                           network_io),
                    "total_untagged_owner": untagged_owner,
                    "total_untagged_team": untagged_team,
                    "total_untagged_work": untagged_work,
                },
                "money_details": {
                    "total_instances_on_demand": total_instances_on_demand,
                    "total_instances_reserved": total_instances_reserved,
                    "total_cost_on_demand": '${:,.2f}'.format(total_cost_on_demand),
                    "total_cost_reserved": '${:,.2f}'.format(total_cost_reserved),
                    "total_cost_simulated_ri": '${:,.2f}'.format(total_cost_simulated_ri),
                    "ri_potential_save": '${:,.2f}'.format(ri_potential_save),
                },
                "low_utilization_instances": {},
                "all_instances:": df.to_dict(orient='records')
            }

            # And adding the low utilization instances DICT into the report...
            if instances_low_utilizations > 0:
                report["low_utilization_instances"] = (df_low.to_dict(orient='records'))
                logger.info("Well done! Not found low utilization instances!!! =) ")

            # Return the final result.
            df_to_picke(df, pick_file)
            return report
        except Exception as e:
            logger.error("Error to create final report... {}".format(e))
            return None
