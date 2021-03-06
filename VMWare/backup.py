from pyVim.connect import SmartConnect, Disconnect
from pexpect import pxssh
from subprocess import call, Popen, PIPE, STDOUT,check_output
import logging
import ssl
import datetime
import mysql.connector
import eventlet
import time
import sys
import os
import hashlib
import magic
#import multiprocessing

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
		sessione.PROMPT = '#'
		Logger.debug("Instauro la connessione ssh su "+ESXSERVER+" con l'utenza "+ESXUSER)
		sessione.login(ESXSERVER, ESXUSER, ESXPASSWORD, login_timeout=2, auto_prompt_reset=False)
		sessione.prompt()
		Logger.debug("Eseguo il comando "+Comando)
		sessione.sendline(Comando)
		sessione.prompt(timeout=30000)
		Logger.debug("Catturo l'esito del comando")
		sessione.sendline('echo $?')
		sessione.prompt(timeout=30000)
		Result = (sessione.before).splitlines()
		Finale = Result[-2]

	except:
		Logger.error("Errore durante la connessione al server "+ESXSERVER)
		Finale = '9999'

	return Finale

def FileType (whichfile) :

	MagicProc = magic.open(magic.MAGIC_NONE)
	MagicProc.load()
	Type = MagicProc.file(whichfile)
	MagicProc.close()

	return  Type


#####################################################################
############################ Variabili ##############################
#####################################################################

with open('/root/.my.cnf') as cnf:
	for line in cnf:
		if 'user' in line:
			SqlUser = line.split("=")[-1]
		if 'password' in line:
			SqlPwd = line.split("=")[-1]
		if 'database' in line:
			SqlDb = line.split("=")[-1]

CriptoKey = os.environ['CRIPTOKEY']
ESXSERVER = sys.argv[1]
ESXUSER = sys.argv[2]
ESXVM = sys.argv[3]


try :
	Logger.debug("Collego al db per ottener al password per l'utente "+ESXUSER+" per il server "+ESXSERVER)
	DBConnection = mysql.connector.connect(user=SqlUser, password=SqlPwd, database=SqlDb)
	Cursor = DBConnection.cursor()
	QueryPwdList = (CriptoKey,ESXSERVER,ESXUSER)
	QueryPwd = "Select AES_DECRYPT(pwd,%s) from T_Secrets where host=%s and user=%s"
	Cursor.execute(QueryPwd,QueryPwdList)
	QueryOutput = Cursor.fetchone()
	Cursor.close()
	DBConnection.close()
	ESXPASSWORD = QueryOutput[0].decode('utf-8')

except :
	Logger.error("Impossibile ottenere la password dell'utente")
	StatoFinale = "999"

certificato = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
certificato.verify_mode = ssl.CERT_NONE

Logger.debug('Instauro connessione verso '+ESXSERVER)
connection = SmartConnect(host=ESXSERVER, user=ESXUSER, pwd=ESXPASSWORD ,sslContext=certificato)

datacenter = connection.content.rootFolder.childEntity[0]
vms = datacenter.vmFolder.childEntity

Logger.debug('Estraggo i dati relativi alla VM '+ESXVM)
for vm in vms :
	if vm.name == ESXVM:
		OSType = vm.config.guestFullName
		VMID = ((str(vm.summary.vm)).split(":")[-1]).translate(None,"'")
		DataStoreVMX = vm.datastore[0]
		DataStoreVMXName = DataStoreVMX.name
		VMX=((vm.config.files.vmPathName).split(" ")[1] )
		PathVMX = "/vmfs/volumes/" + DataStoreVMXName + "/" + VMX
		VirtualDevice = vm.config.hardware.device
		ListDisk = []
 		for Device in VirtualDevice :
			if hasattr(Device.backing, 'fileName') :
				DataStoreName = Device.backing.datastore.name
				DiskFileName = ((Device.backing.fileName).split(" ")[-1])
				PathVMDK = "/vmfs/volumes/" + DataStoreName + "/" + DiskFileName
				ListDisk.append(PathVMDK,)
Disconnect(connection)

DataBackup = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
DataBackupTxt = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
DataStoreBackup = "CC_Backup_" + ESXVM + "_" + DataBackup
DataStoreBackupPath = "/vmfs/volumes/" + DataStoreBackup
LocalBackupFolderPath = "/Backup/VMWare/" + ESXVM + "/" + DataBackup
BackupId = ESXSERVER + "-" + ESXVM + "-" + DataBackup
PID = str(os.getpid())

Logger.debug('Data del backup : '+DataBackup)
Logger.debug('Datastore di backup : '+DataStoreBackup)
Logger.debug('Path del datastore di backup : '+DataStoreBackupPath)
Logger.debug('Path locale della folder di backup : '+LocalBackupFolderPath)
Logger.debug("VM id : "+VMID)
Logger.debug("Paht del VMX : "+PathVMX)
for disk in ListDisk:
	Logger.debug('Per la VM '+ESXVM+' backuppo il bakcup di :'+disk)

#####################################################################
############################ Programma ##############################
#####################################################################
Logger.debug("Creo l'ID del backup nel db")
DBConnection = mysql.connector.connect(user=SqlUser, password=SqlPwd, database=SqlDb)
Cursor = DBConnection.cursor()
QueryBackupIDList = (BackupId,DataBackup,"1",PID,ScriptName)
QueryBackupID =  "INSERT INTO T_Jobs (jobid,datejob,status,pid,script) VALUES (%s,%s,%s,%s,%s)"
Cursor.execute(QueryBackupID,QueryBackupIDList)
Cursor.close()
DBConnection.commit()
DBConnection.close()

# 0 - Creo la cartella di backup e ne configuro l'export in NFS
Logger.debug("Inizio fase 0")
if not os.path.exists(LocalBackupFolderPath):
    os.makedirs(LocalBackupFolderPath)

NFSExport = LocalBackupFolderPath + " " + ESXSERVER + "(rw,no_root_squash)\r\n"
with open("/etc/exports", "a") as nfsexportsfile:
    nfsexportsfile.write(NFSExport)
Logger.debug("Ricarico la configurazione dell'NFS")
call(["exportfs","-ra"])

# 1 - Montare Datastore di backup
Logger.debug("Inizio fase 1 - Aggiungo Datastore per il backup")
Comando1 = "esxcfg-nas --add " + DataStoreBackup + " --host xxx.xxx.xxx.xxx --share " + LocalBackupFolderPath
Fase1 = ESXCOMMAND(Comando1)
Logger.debug("Fase1 e terminata con il codice : "+Fase1)
# 2 - Creare lo snapshot della VM
Logger.debug("Inizio Fase 2 - Creo Snapshot della VM")
if (Fase1) and (Fase1 == "0"):
	Comando2 = "vim-cmd vmsvc/snapshot.create " + VMID +" 'CCBackup' 'Backup effettuato il " + DataBackupTxt + "'" # 0 0"
	Fase2 = ESXCOMMAND(Comando2)
	Logger.debug("Fase 2 e terminata con il codice : "+Fase2)
else :
	Logger.warn("Fase 2 non e stata avviata")
# 3 - Clonare i dischi (se piu in parallelo)
Logger.debug("Inizio Fase 3 - Clonazione dei dischi")
if (Fase2) and (Fase2 == "0"):
	Fase3AllResult = []
	Comando3VMX = "cp " + PathVMX + " " + DataStoreBackupPath
	Fase3VMX = ESXCOMMAND(Comando3VMX)
	Logger.debug("Backup del vmx terminato con il codice : "+Fase3VMX)
	for Disk in ListDisk :
		Logger.debug("Inizio clonazione del disco : "+Disk)
		if Disk.split(".")[-1] == "vmdk" :
			Comando3VMDK = "vmkfstools -d thin -i "+ Disk + " " + DataStoreBackupPath + "/" + Disk.split("/")[-1]
			Fase3VMDK = ESXCOMMAND(Comando3VMDK)
			Fase3AllResult.append(Fase3VMDK,)
			Logger.debug("Clonazione del disco "+Disk+" termninata con codice : "+Fase3VMDK)
		else :
			Comando3Other = "cp " + Disk + " " + DataStoreBackupPath
			Fase3Other = ESXCOMMAND(Comando3Other)
			Fase3AllResult.append(Fase3Other,)
			Logger.debug("Backup di "+Disk+" terminato con codice :"+Fase3Other)
else :
	Logger.warn("Fase 3 non e stata avviata")
# 4 - Rimuovere lo snapshot
Logger.debug("Inizio Fase 4 - Rimozione dello snashot")
if (Fase2) and (Fase2 == "0"):
	Comando4 = "vim-cmd vmsvc/snapshot.removeall " + VMID
	Fase4 = ESXCOMMAND(Comando4)
	Logger.debug(" Fase 4 terminata con codice : "+Fase4)
# 5 - Smontare il Datastore di backup
Logger.debug("Inizio Fase 5 - Smontaggio Datastore di Backup")
if (Fase1) and (Fase1 == "0"):
	Comando5 = "esxcfg-nas --delete " + DataStoreBackup
	Fase5 = ESXCOMMAND(Comando5)
	Logger.debug('Fase 5 terminata con codice : '+Fase5)
else :
	Logger.debug("Fase 5 non e stata avviata")
# 6 - Lancio con processo a parte l'indicizzazione dei file nei dischi
Logger.debug("Inizio Fase 6 - Indicizzazione dei file di bakcup")
Logger.debug("Apro connessione al db")
DBConnection = (user=SqlUser, password=SqlPwd, database=SqlDb)
Cursor = DBConnection.cursor()
if "Windows" in OSType:
	for Disk in ListDisk :
		if Disk.split(".")[-1] == "vmdk" :
			Logger.debug("Monto il file "+Disk)
			print (datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S") + " : Monto il file "+Disk)
			Mountpoint = "/mnt/"+ESXVM+"/"+DataBackup
			DiskFlat = (Disk.split("/")[-1]).split(".")[0] + "-flat.vmdk"
			os.makedirs(Mountpoint)
			LosetupOption =  LocalBackupFolderPath + "/" + DiskFlat
			NewLoop = (check_output(["losetup","-f"])).splitlines()[0]
			Logger.debug("Ottengo il prossimo loop libero : "+NewLoop)
			LosetupOutput = check_output(["losetup","-r",NewLoop,LosetupOption])
			Logger.debug("Risultato del losetup : "+LosetupOutput)
			KpartxOutput = check_output(["kpartx","-av",NewLoop])
			Logger.debug("Risultato del kaprtx : "+KpartxOutput)
			output = check_output(["kpartx","-l",NewLoop])
			for partition in output.splitlines():
				Count = 0
				Querylist = []
				if partition:
					Loop = partition.split(" ")[0]
					Partition2Mount = "/dev/mapper/" + Loop
					Logger.debug("Monto la partizione "+Partition2Mount+" sul mountpoint "+Mountpoint)
					call(["mount",Partition2Mount,Mountpoint])
					Query = "INSERT INTO T_FileBackup (backupid,host,vm,vmdk,part,filename,filetype,directory,md5,datebackup) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
					for root, dirnames, filenames in os.walk(Mountpoint):
						for filename in filenames :
							Logger.debug("Calcolo MD5 per il file "+filename)
							try:
								TypeFile = FileType(root + "/" + filename)
								if TypeFile != "fifo (named pipe)":
									with eventlet.timeout.Timeout(10):
										Filebin = open(root + "/" + filename, "rb")
										MD5 = hashlib.md5(Filebin.read()).hexdigest()
										Filebin.close()
								else:
									MD5 = "NoMD5Computing"
							except:
								MD5 = "ErroreInMD5OpenFile"
							Directory = root.replace(Mountpoint,"")
							if Count < 1000 :

								Querylist.append((BackupId,ESXSERVER,ESXVM,DiskFlat,Loop,filename,TypeFile,Directory,MD5,DataBackup), )
								Count += 1
							else :
								Logger.debug("Eseguo la query per aver raggiunto i 1000 record")
								Cursor.executemany(Query,Querylist)
								Cursor.close()
								Logger.debug("Committo la query sul db")
								DBConnection.commit()
								Cursor = DBConnection.cursor()
								Count = 0
								Querylist = []
					Logger.debug("Eseguo la query finale per la partizione "+Loop)
					Cursor.executemany(Query,Querylist)
					Logger.debug("Smonto "+Mountpoint)
					call(["umount",Mountpoint])
			Logger.debug("Rimuovo i volumi creati da loopsetup")
			Logger.debug("Rimuovo quanto creato con kpartx")
			call(["kpartx","-dv",NewLoop])
			time.sleep(5)
			Logger.debug("Smonto la loop")
			call(["losetup","-d",NewLoop])
			time.sleep(5)
			Logger.debug("Rimuovo la directory di mount "+Mountpoint)
			os.rmdir(Mountpoint)
Logger.debug("Aggiorno lo stato del job sul db")
if (Fase1 == "0") and (Fase1 == "0") and (Fase2 == "0") and (Fase3VMX == "0") and ( Fase4 == "0") and (Fase5 == "0") and (all(Result == "0" for Result in Fase3AllResult) or Fase3AllResult == [] ):
	StatoFinale = "0"
else :
	StatoFinale = "999"

QueryUpdateBackupIDList = (StatoFinale,BackupId)
QueryUpdateBackupID = "UPDATE T_BackkupID SET status=%s WHERE backupid=%s"
QueryUpdateBackupID = "UPDATE T_Jobs SET status=%s WHERE jobid=%s"
Cursor.execute(QueryUpdateBackupID,QueryUpdateBackupIDList)

Cursor.close()
Logger.debug("Commit finale sul DB")
DBConnection.commit()
Logger.debug("Chiudo la connessione al DB")
DBConnection.close()
Logger.debug("Job di backup utlimato")
