import mysql.connector
import logging
import sys
import os
import datetime

############################# Logging ###############################

LogFile = '/var/log/CentralConsole/CentralConsole.log'

ScriptName = ((sys.argv[0]).split("/")[-1]).split(".")[0]
Logger = logging.getLogger(ScriptName)
Logger.setLevel(logging.DEBUG)

FileHandler = logging.FileHandler(LogFile)
FileHandler.setLevel(logging.DEBUG)

LogFormat = logging.Formatter('%(asctime)s | %(name)s | %(process)d | %(levelname)s | %(message)s')
FileHandler.setFormatter(LogFormat)

Logger.addHandler(FileHandler)
#####################################################################

#####################################################################
############################# Funzioni ##############################
#####################################################################



#####################################################################
############################ Variabili ##############################
#####################################################################

with open('/root/.my.cnf') as cnf:
	for line in cnf:
		if 'user' in line:
			SqlUser = (line.split("=")[-1]).strip('\n')
		if 'password' in line:
			SqlPwd = (line.split("=")[-1]).strip('\n')
		if 'database' in line:
			SqlDb = (line.split("=")[-1]).strip('\n')

ESXSERVER = sys.argv[1]
ESXUSER = sys.argv[2]
PASSWORD = sys.argv[3]

CriptoKey = os.environ['CRIPTOKEY']

DataJob = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
PID = str(os.getpid())
JobId = ESXSERVER + "-" + ESXUSER + "-" + DataJob

#####################################################################
############################ Programma ##############################
#####################################################################

Logger.debug("Creo l'ID del backup nel db")
Logger.debug("Apro connessione al DB")
DBConnection = mysql.connector.connect(user=SqlUser, password=SqlPwd, database=SqlDb)
Cursor = DBConnection.cursor()
QueryJobIdList = (JobId,DataJob,"1",PID,ScriptName)
QueryJobId =  "INSERT INTO T_Jobs (jobid,datejob,status,pid,script) VALUES (%s,%s,%s,%s,%s)"
Cursor.execute(QueryJobId,QueryJobIdList)
Cursor.close()
DBConnection.commit()

Logger.debug("Controllo se le credenziali esistono gia")

Cursor = DBConnection.cursor()
QueryCheck = "Select AES_DECRYPT(pwd,%s) from T_Secrets where host=%s and user=%s"
QueryCheckList = (CriptoKey,ESXSERVER,ESXUSER)
Cursor.execute(QueryCheck,QueryCheckList)
Check = Cursor.fetchone()
Cursor.close()


if Check == None :
    Logger.debug("Inserisco le nuove credenziali")

    Cursor = DBConnection.cursor()

    QueryInsertCredential = "INSERT INTO T_Secrets (host,user,pwd) VALUES (%s,%s,AES_ENCRYPT(%s,%s))"
    QueryInsertCredentialList = (ESXSERVER,ESXUSER,PASSWORD,CriptoKey)
    Cursor.execute(QueryInsertCredential,QueryInsertCredentialList)
    DBConnection.commit()
    Cursor.close()
    StatoFinale = '0'

else :
    Logger.warn("Credenziali gia esistenti")
    StatoFinale = '990'

Cursor = DBConnection.cursor()
QueryUpdateJobIdList = (StatoFinale,JobId)

Logger.debug("Aggiorno lo stato del job a "+StatoFinale)
QueryUpdateJobId = "UPDATE T_Jobs SET status=%s WHERE jobid=%s"
Cursor.execute(QueryUpdateJobId,QueryUpdateJobIdList)
Cursor.close()
DBConnection.commit()
Logger.debug("Chiudo connessione al DB")
DBConnection.close()
