rom
libs.db_mongo
import Mongo
# from libs.db_rethink import Rethink
import logging
from api_config import log_config
# from libs.db_rethink import Rethink
import logging

from api_config import log_config
from libs.db_mongo import Mongo

logging.config.dictConfig(log_config)
logger = logging.getLogger("db_wrapper")


class DataStore(object):
    mongo = None
    rethink = None

    def __init__(self):
        self.mongo = Mongo()
        #self.rethink = Rethink()
        pass

    def save(self, db, table, data):
        try:
            result = self.mongo.save(db, table, data)
            if result:
                logger.debug("Inserted into DB: {}...")
            else:
                logger.debug("It's not error but not inserted nothing on DB")
        except Exception as e:
            logger.exception("Saving error  - {}".format(e))
            logger.error("Fail on save this information: {}".format(data))

    def get_low_utilization_db(self, db, table, instance_id=None, instance_region=None, tag_key=None, tag_value=None,
                               summary_report=None):
        try:
            rs = self.mongo.get_low_utilizaion_db(db, table, instance_id, instance_region, tag_key, tag_value,
                                                  summary_report)
            return rs[0]
        except Exception as e:
            logger.error("Error on get data {}".format(e))
