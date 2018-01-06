import logging

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from api_config import main_config, log_config

logging.config.dictConfig(log_config)
logger = logging.getLogger("db_mongo")


class Mongo(object):
    mongo_db = None
    conn = None

    def __init__(self, mongo_server=None, mongo_port=27017):
        try:
            try:
                if mongo_server is None:
                    mongo_server = main_config["mongo-server"]
                client = MongoClient("mongodb://{}".format(mongo_server))
                self.conn = client
            except Exception as e:
                logger.error("Error to connect MongoDB : {}".format(e))

        except Exception as e:
            logger.error("Erro ao conectar no hostname: {0} - {1}".format(mongo_server, e))

    def save(self, mongo_db, mongo_collection, data):
        try:
            db = self.conn[mongo_db][mongo_collection]
            inserted = db.insert_one(data)
            logger.info("Data has been inserted with success in MongoDB : {0}".format(inserted))
            return inserted

        except PyMongoError as e:
            logger.error("Error on insert data - Mongodb {}".format(e))
            logger.info("I have tried to write this data: {}".format(data))
        finally:
            try:
                self.conn.close()
                logger.debug("Connection with mongo has finished")
                pass
            except Exception as e:
                logger.error("Error to finish MongoDB connection: {}".format(e))
                exit(1)

    def get_low_utilizaion_db(self, mongo_db, mongo_collection, instance_id=None, instance_region=None, tag_key=None,
                              tag_value=None):
        try:
            db = self.conn[mongo_db][mongo_collection]
            documents = None
            if tag_key is not None and tag_value is not None:
                # documents = db.aggregate({"$match": {"instances.{}".format(tag_key): tag_value}}).sort("_id", -1).limit(1)
                documents = db.find({"instances.{}".format(tag_key): tag_value}, {"instances.$": 1}).sort("_id",
                                                                                                          -1).limit(1)
                result = [(item) for item in documents]

            else:
                documents = db.find().sort("_id", -1).limit(1)
                result = [(item) for item in documents]

            return result
        except Exception as e:
            logger.error("Error on Mongo get_low_utilizaion_db - {}".format(e))
        finally:
            try:
                self.conn.close()
                logger.debug("Connection with mongo has finished")
                pass
            except Exception as e:
                logger.error("Error to finish MongoDB connection: {}".format(e))
                exit(1)
