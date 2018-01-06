rom
libs.db_mongo
import Mongo
# from libs.db_rethink import Rethink
import logging
# from libs.db_rethink import Rethink
import logging

from libs.db_mongo import Mongo


class DataStore(object):
    mongo = None
    rethink = None

    def __init__(self):
        self.mongo = Mongo()
        # self.rethink = Rethink()
        pass

    def save(self, db, table, data):
        try:
            result = self.mongo.save(db, table, data)
            if result:
                logging.debug("Inserted into DB: {}...")
            else:
                logging.debug("It's not error but not inserted nothing on DB")
        except Exception as e:
            logging.error("Saving error  - {}".format(e))

    def get_low_utilization_db(self, db, table, instance_id=None, instance_region=None, tag_key=None, tag_value=None):
        try:
            rs = self.mongo.get_low_utilizaion_db(db, table, instance_id, instance_region, tag_key, tag_value)
            return rs[0]
        except Exception as e:
            logging.error("Error on get data {}".format(e))
