from pyVim.connect import SmartConnect, Disconnect
from pexpect import pxssh
from subprocess import call, Popen, PIPE, STDOUT,check_output
import logging
import ssl
import datetime
import mysql.connector
import eventlet
import sys
import os
import hashlib
import multiprocessing

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

def ESXCOMMAND(Comando):
	try:

		sessione = pxssh.pxssh()
		sessione.force_password = True
		sessione.PROMPT = ' # '
		Logger.debug("Starting ssh connection on "+ESXSERVER+" with user "+ESXUSER)
		sessione.login(ESXSERVER, ESXUSER, ESXPASSWORD, login_timeout=2, auto_prompt_reset=False)
		sessione.prompt()
		Logger.debug("Run: "+Comando)
		sessione.sendline(Comando)
		sessione.prompt(timeout=30000)
		Logger.debug("Get command output")
		sessione.sendline('echo $?')
		sessione.prompt(timeout=30000)
		Result = (sessione.before).splitlines()
		Finale = Result[-2]

	except:
		Logger.error("Error during connection on server "+ESXSERVER)
		Finale = '9999'

	return Finale


#####################################################################
############################ Variabili ##############################
#####################################################################
CriptoKey = os.environ['CRIPTOKEY']
ESXSERVER = sys.argv[1]
ESXUSER = sys.argv[2]
PID = str(os.getpid())

with open('/root/.my.cnf') as cnf:
	for line in cnf:
		if 'user' in line:
			SqlUser = (line.split("=")[-1]).strip('\n')
		if 'password' in line:
			SqlPwd = (line.split("=")[-1]).strip('\n')
		if 'database' in line:
			SqlDb = (line.split("=")[-1]).strip('\n')
try :
	Logger.debug("Connection on db to get password for user "+ESXUSER+" for the server "+ESXSERVER)
	DBConnection = mysql.connector.connect(user=SqlUser,password=SqlPwd,database=SqlDb)
	Cursor = DBConnection.cursor()
	QueryPwdList = (CriptoKey,ESXSERVER,ESXUSER)
	QueryPwd = "Select AES_DECRYPT(pwd,%s) from T_Secrets where host=%s and user=%s"
	Cursor.execute(QueryPwd,QueryPwdList)
	QueryOutput = Cursor.fetchone()
	Cursor.close()
	DBConnection.close()
	ESXPASSWORD = QueryOutput[0].decode('utf-8')

except :
	Logger.error("Impossible get user password")
	StatoFinale = "999"

DataJob = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
JobId = ESXSERVER + "-" + ESXUSER + "-" + DataJob

#####################################################################
############################ Programma ##############################
#####################################################################

Logger.debug("Creating job ID")
DBConnection = mysql.connector.connect(user=SqlUser,password=SqlPwd,database=SqlDb)
Cursor = DBConnection.cursor()
QueryJobIdList = (JobId,DataJob,"1",PID,ScriptName)
QueryJobId =  "INSERT INTO T_Jobs (JobId,datejob,status,pid,script) VALUES (%s,%s,%s,%s,%s)"
Cursor.execute(QueryJobId,QueryJobIdList)
Cursor.close()
DBConnection.commit()
DBConnection.close()

Logger.debug("Starting Fase 1 - Files renaming ")
Comando1a = "mv /etc/vmware/vmware.lic /etc/vmware/vmware.lic."+DataJob
Fase1a = ESXCOMMAND(Comando1a)
Logger.debug("Fase 1a ended with exit code : "+Fase1a)
if Fase1a == "0":
	Comando1b = "mv /etc/vmware/license.cfg /etc/vmware/license.cfg."+DataJob
	Fase1b = ESXCOMMAND(Comando1b)
else :
	Fase1b = "990"
Logger.debug("Fase 1b ended with exit code : "+Fase1b)

Logger.debug("Starting Fase 2 - Coping template files")
if Fase1b == "0":
	Comando2a = "cp /etc/vmware/.#license.cfg /etc/vmware/license.cfg"
	Fase2a = ESXCOMMAND(Comando2a)
else :
	Fase2a = "990"
Logger.debug("Fase 2a ended with exit code : "+Fase2a)
if Fase2a == "0":
	Comando2b = "cp /etc/vmware/.#vmware.lic /etc/vmware/vmware.lic"
	Fase2b = ESXCOMMAND(Comando2b)
else :
	Fase2b = "990"
Logger.debug("Fase 2b ended with exit code : "+Fase2b)

Logger.debug("Starting Fase 3 - Services Restart")
if Fase2b == "0":
	Comando3 = "/etc/init.d/vpxa restart"
	Fase3 = ESXCOMMAND(Comando3)
else:
	Fase3 = "990"
Logger.debug("Fase 3 ended with exit code : "+Fase3)

if (Fase1a == "0") and (Fase1b == "0") and (Fase2a == "0") and (Fase2b == "0") and (Fase3 == "0"):
	StatoFinale = "0"
else :
	StatoFinale = "999"

DBConnection = mysql.connector.connect(user=SqlUser,password=SqlPwd,database=SqlDb)
Cursor = DBConnection.cursor()
QueryUpdateJobIdList = (StatoFinale,JobId)
QueryUpdateJobId = "UPDATE T_Jobs SET status=%s WHERE jobid=%s"
Cursor.execute(QueryUpdateJobId,QueryUpdateJobIdList)

Cursor.close()
Logger.debug("Final Commit on DB")
DBConnection.commit()
Logger.debug("Closing connection on db")
DBConnection.close()
Logger.debug("Job ended")

print StatoFinale

