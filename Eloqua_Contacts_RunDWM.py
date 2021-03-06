import dwm
from datetime import datetime
import sys, os, logging
from pymongo import MongoClient
from collections import OrderedDict
from pyqm import Queue, clean
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

###############################################################################
## Load custom functions
###############################################################################

from custom import CleanZipcodeUS, CleanAnnualRevenue

###############################################################################
## Setup logging
###############################################################################

## setup job name
jobName = 'Eloqua_Contacts_DWM_RUN'
metricPrefix = 'BATCH_MINUTELY_ELOQUA_DWM_'

## Setup logging
logname = '/' + jobName + '_' + format(datetime.now(), '%Y-%m-%d') + '.log'
logging.basicConfig(filename=os.environ['OPENSHIFT_LOG_DIR'] + logname, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
jobStart = datetime.now()

env = os.environ['OPENSHIFT_NAMESPACE']

###############################################################################
## Open queue and get contacts therein
###############################################################################

clientQueue = MongoClient(os.environ['MONGODB_URL'])

dbQueue = clientQueue['dwmqueue']

exportQueue = Queue(db = dbQueue, queueName = 'dwmQueue')

size = exportQueue.getAvailSize()

logging.info('Records waiting in queue: ' + str(size))

total = 0

if size>0:

    indicatorQueue = Queue(db = dbQueue, queueName = 'indicatorQueue')

    job = exportQueue.next(job = jobName + '_' + format(datetime.now(), '%Y-%m-%d'), limit = 600)

    logging.info('current job size: ' + str(len(job)))

    total = len(job)

    ###############################################################################
    ## Retrieve DWM configuration
    ###############################################################################

    ## In some cases (including ours), the actual ordering of the 'fields' subdoc of config is order-dependant
    ## i.e., if the "Persona" field is dependant on having a valid value in "Job Role", then any cleaning rules should be applied to "Job Role" first

    ## To make sure this is the case, we connect to MongoDB first specifying document_class=OrderedDict
    ## This will preserve the ordering of fields

    ## Reason for using a different connection: specifying document_class in the MongoClient will slowwwww the rest of the queries for DWM.
    ## So, just close it out and create a new connection to pass to DWM

    clientConfig = MongoClient(os.environ['MONGODB_URL'], document_class=OrderedDict)
    dbConfig = clientConfig['dwmdev']

    config = dbConfig.config.find_one({"configName": "Eloqua_Contacts_DWM"})

    logging.info("Retrieved config from MongoDB as an OrderedDict")

    clientConfig.close()

    ###############################################################################
    ## Run the DWM
    ###############################################################################

    ## connect to mongo
    client = MongoClient(os.environ['MONGODB_URL'])
    db = client['dwmdev']
    logging.info("Connected to mongo")

    ## Run DWM
    dwmStart = datetime.now()
    dataOut = dwm.dwmAll(data=job, db=db, config=config, udfNamespace=__name__, verbose=True)
    dwmEnd = datetime.now()

    client.close()

    ###############################################################################
    ## Put them into the processedQueue; remove from exportQueue
    ###############################################################################

    indicatorQueue.add(dataOut, transfer=True)

    exportQueue.complete(job)

else:

    logging.info("ain't no fish here")

jobEnd = datetime.now()
jobTime = (jobEnd-jobStart).total_seconds()
try:
    dwmTime = (dwmEnd-dwmStart).total_seconds()
except:
    dwmTime = 0

## Push monitoring stats to Prometheus
registry = CollectorRegistry()
g = Gauge(metricPrefix + 'last_success_unixtime', 'Last time a batch job successfully finished', registry=registry)
g.set_to_current_time()
l = Gauge(metricPrefix + 'total_seconds', 'Total number of seconds to complete job', registry=registry)
l.set(jobTime)
t = Gauge(metricPrefix + 'total_records_total', 'Total number of records processed in last batch', registry=registry)
t.set(total)
z = Gauge(metricPrefix + 'total_seconds_dwm', 'Total number of seconds to complete DWM processing', registry=registry)
z.set(dwmTime)

push_to_gateway(os.environ['PUSHGATEWAY'], job=jobName, registry=registry)
