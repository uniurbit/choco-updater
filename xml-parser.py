# FB @ UniUrb 20201210
# UniUrb choco update-feeder
''' 
e.g. python xml-parser.py check
mode : check
    From a package list defined in database tbl 'package'  
    the script makes HTTP GET to Chocolatey community API
    just to check latest version of each package and update database.
mode : upgrade
    Runs pending updates then set as updated 
mode : init
    migrate query structure in local sqlite3 db
    seed query structure in local sqlite3 db
mode : status
    show list of upgradable packages
'''
import requests
import lxml.etree
import datetime
#import mysql.connector
from termcolor import colored
import sys
import subprocess
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
import sqlite3
from dbstruct import *
from secrets import *
from colorama import init

version = '2020.12.18.002'
init()
debug = 1
# debug level 
# 1 standard
# 2 standard + dump xml2dict 

errors = 0
warns = 0
subject = '[ DONE ] Choco check_updates'
msg = 'No operation'

nsmap = {
  'm': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata',
  'd': 'http://schemas.microsoft.com/ado/2007/08/dataservices'
}

m_null = ('{%s}null' % nsmap['m'])
m_type = ('{%s}type' % nsmap['m'])

type_handlers = {
    'Edm.Double': float,
    'Edm.Int32': int,
    #'Edm.DateTime': lambda s: datetime.datetime.strptime(s.translate({ord(i):None for i in ':-'}), "%Y%m%dT%H%M%S.%f"),
}

def db_connect(db):
    global errors
    global msg
    conn = None
    try:
        #conn = mysql.connector.connect(user='choco', password='ocohc', host='127.0.0.1', database='choco_update', auth_plugin='caching_sha2_password')
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        return conn
    #except mysql.connector.Error as e:
    #    if(debug): print(colored('[ ERROR ]', 'magenta'), 'MySQL connection : ')
    #    print(e)
    #    errors += 1
    #    msg = msg + '\n' + ('Error in MySQL connection {}').format(e)
    except sqlite3.Error as e:
        if(debug): print(colored('[ ERROR ]', 'magenta'), 'SQL (db_connect) : ')
        print(e)
        errors += 1
        msg = msg + '\n' + ('Error in SQL (db_connect) {}').format(e)
    return conn

def create_db_struct(conn):
    global errors
    global msg
    if(conn is not None):
        try:
            cursor = conn.cursor()
            # migration
            cursor.execute(create_tbl_package)
            cursor.execute(create_tbl_package_update)
            cursor.execute(create_tbl_status)
            # seed
            cursor.execute(insert_tbl_status)
            conn.commit()
        except sqlite3.Error as e:
            if(debug): print(colored('[ ERROR ]', 'magenta'), 'SQL (create_db_struct) : ')
            print(e)
            errors += 1
            msg = msg + '\n' + ('Error in SQL (create_db_struct) {}').format(e)

def insert_package():
    '''
    query : puts pkg info into db
    name : pkg name
    description : pkg decription
    choco_id : pkg chocolatey id, in order to retrieve pkg infos from api  
    '''
    query = ("INSERT OR IGNORE INTO package"
            " (name, description, choco_id)"
            " VALUES (?, ?, ?)")
    if(debug) : print(colored('[ INFO ]', 'cyan'), 'SQL query (insert_package) : ', query)
    return query

def insert_pending_update():
    '''
    query : adds a pkg update with pending status
    package_id : pkg id from package table
    version : pkg chocolatey version from api
    fetch_timestamp : fetch_timestamp
    '''
    # 1 pending
    query = ("INSERT OR IGNORE INTO pkg_update"
            " (package_id, version, fetch_timestamp, status_id)"
            " VALUES (?, ?, ?, 1)")
    if(debug) : print(colored('[ INFO ]', 'cyan'), 'SQL query (insert_pending_update) : ', query)
    return query

def get_all_pending_updates():
    '''
    query : pending packages
    '''
    query = ("SELECT DISTINCT package.name, * FROM pkg_update JOIN package ON pkg_update.package_id=package.id WHERE status_id=1 ORDER BY package.name, fetch_timestamp")
    if(debug) : print(colored('[ INFO ]', 'cyan'), 'SQL query (get_all_pending_updates) : ', query)
    return query

def get_update_data():
    '''
    query : if exists, the update by package and version
    package_id : package_id
    version : version_id
    '''
    query = ("SELECT pkg_update.*, status.name AS sname FROM pkg_update JOIN status ON pkg_update.status_id=status.id WHERE package_id=? AND version=?")
    if(debug) : print(colored('[ INFO ]', 'cyan'), 'SQL query (get_update_data) : ', query)
    return query

def get_package_data(single=0):
    '''
    query : uniurb's choco packages list
    '''
    query = "SELECT * FROM package"
    if(single == 1):
        query = query + " WHERE choco_id=?"
    if(debug): print(colored('[ INFO ]', 'cyan'), 'SQL query (get_package_data) : ', query)
    query = query + " ORDER BY name"
    return query

def get_latest_version():
    '''
    query : get package latest version
    '''
    query = "SELECT * FROM package JOIN pkg_update ON package.id=pkg_update.package_id WHERE choco_id=? AND status_id <> 1 ORDER BY version DESC LIMIT 1"
    if(debug): print(colored('[ INFO ]', 'cyan'), 'SQL query (get_package_data) : ', query)
    return query

def set_update_package():
    '''
    query: updates pkg status 
    update_timestamp : update_timestamp
    package_id : pkg id from package table
    version : pkg chocolatey version from api
    '''
    # 2 updated
    query = ("UPDATE pkg_update SET"
            " update_timestamp=?, status_id=2"
            " WHERE package_id=? AND version=?")
    if(debug) : print(colored('[ INFO ]', 'cyan'), 'SQL query (set_update_package) : ', query)
    return query

def set_skip_package():
    '''
    query: skip pkg update only for pending package_id
    package_id : pkg id from package table
    '''
    # 3 skipped
    query = ("UPDATE pkg_update SET"
            " status_id=3"
            " WHERE package_id=? AND status_id=1")
    if(debug) : print(colored('[ INFO ]', 'cyan'), 'SQL query (set_skip_package) : ', query)
    return query

def translate_update_status():
    '''
    query: decode status
    id: status_id
    '''
    query = ("SELECT * FROM status WHERE id=?")
    if(debug) : print(colored('[ INFO ]', 'cyan'), 'SQL query (translate_update_status) : ', query)
    return query

def xml2dict(xml_file, multilevel=0):
    #root = lxml.etree.parse(xml_file)
    root = lxml.etree.fromstring(xml_file)
    result = {}
    i = 1
    for prop in root.xpath('//m:properties', namespaces=nsmap):
        if(multilevel): result[i] = {}
        for child in prop.getchildren():
            tag = (child.tag.split('}',1)[-1]).lower()
            if child.attrib.get(m_null):
                value = None
                if(debug == 2) : print('>>>>>', tag, ' - ', value)
            else:
                value = child.text
                if(debug == 2) : print('>>>>>', tag, ' - ', value)
                type_handler = type_handlers.get(child.attrib.get(m_type))
                if type_handler is not None:
                    value = type_handler(value)
            if(multilevel):
                result[i][tag] = value
            else:
                result[tag] = value
            if(debug == 2) : print('<<<<<', tag, ' - ', value)
        i += 1
    return result

def event_trigger(notify=0, sub='', msg='', command=''):
    if(notify):
        fro = from_mail
        to = to_mail
        m = MIMEMultipart("alternative")
        m['From'] = fro
        m['To'] = to
        m['Date'] = formatdate(localtime=True)
        m['Subject'] = sub

        m.attach(MIMEText(msg, "plain"))

        try: 
            smtp = smtplib.SMTP(smtp_host)
            smtp.login(smtp_user, smtp_password)
            smtp.sendmail(fro, to, m.as_string())
            smtp.close()
        except Exception as e:
            if(debug) : print(colored('[ ERROR ]', 'magenta'), 'SMTP (event_trigger) : ')
            print(e)
    if(len(command) > 0):
        print('COMMAND:', command)
        subprocess.call(command, shell=True)

def sync_repo_package(conn):
    '''
    makes an HTTP GET request to local repo in order to get all available packages
    then insert, if not exists, the package infos into the db
    '''
    global errors
    global msg
    global subject
    global warns
    global errors
    global already_in
    subject = '[ DONE ] Choco sync_repo_package'
    msg = ''
    already_in = 0
    try:
        cursor = conn.cursor()
        url = choco_local_latest_repo
        response = requests.get(url)
        if(debug):
            print(colored('[ INFO ]', 'cyan'), 'Getting packages info from local repo')
            print(colored('[ INFO ]', 'cyan'), 'Fetch url : ', url) 
        data = xml2dict(response.content, 1)
        if(debug): print(colored('[ INFO ]', 'cyan'), len(data), 'packages were found')
        for i in data:
            cursor.execute(insert_package(), (data[i]['title'], data[i]['summary'], data[i]['id']))
            conn.commit()
            if(cursor.rowcount <= 0): 
                check = cursor.execute(get_package_data(1), (data[i]['id'],))
                if(check.fetchone() is None):
                    if(debug): print(colored('[ ERROR ]', 'magenta'), end=' ')
                    errors += 1
                else:
                    if(debug): print(colored('[ INFO ]', 'cyan'), 'Record already exists in db',end=' ')
                    already_in += 1
                    msg = msg + '\n' + ('Package {} \nVersion {} \nAlready in repo\n').format(data[i]['title'], data[i]['version'])
            else:
                print(colored('[ INFO ]', 'cyan'), end=' ')
                if(debug): print('SQL Insert, affected rows : ', cursor.rowcount)
                msg = msg + '\n' + ('Package {} \nVersion {} Insert : {}\n').format(data[i]['title'], data[i]['version'], cursor.rowcount)
            if(debug):
                print(colored('[ INFO ]', 'cyan'), 'id : ', data[i]['id'])
                print(colored('[ INFO ]', 'cyan'), 'title : ', data[i]['title'])
                print(colored('[ INFO ]', 'cyan'), 'version : ', data[i]['version'])
                print(colored('[ INFO ]', 'cyan'), 'summary : ', data[i]['summary'], '\n')
    except sqlite3.Error as e:
        if(debug): print(colored('[ ERROR ]', 'magenta'), 'SQL (sync_repo_package) : ')
        print(e)
        errors += 1
        msg = msg + '\n' + ('Error in SQL (sync_repo_package) {}').format(e)
    finally:
        if(conn is not None):
            cursor.close()
            conn.close()
            if(debug): print(colored('[ INFO ]', 'cyan'), 'SQL Connection closed. bye bye')
        if(warns > 0):
            subject = '[ WARN ] Choco sync_repo_package' 
        if(errors > 0):
            subject = '[ FAIL ] Choco sync_repo_package'
        event_trigger(1, subject, msg)

def package_status_update(conn):
    '''
    return a list of pending packages
    NOTE: maybe a duplicate of client_update
    '''
    msg = ''
    if(conn is not None):
        try:
            conn = db_connect(db_path)
            cursor = conn.cursor()
            cursor.execute(get_all_pending_updates())  
            packages = cursor.fetchall()  
            packages = [dict(row) for row in packages]
            if(len(packages) == 0):
                msg = msg + '\n' + ('No packages marked for update.')
                if(debug): print(colored('[ INFO ]', 'cyan'), 'No packages marked for update.')
            else:
                if(debug): 
                    print(colored('[ INFO ]', 'cyan'), 'vvvvvv Packages marked for update. vvvvvvv\n')
                for p in packages:
                    if(debug):
                        #print(colored('[ INFO ]', 'cyan'), 'Package : ', p)
                        print(colored('[ INFO ]', 'cyan'), 'id : ', p['id'])
                        print(colored('[ INFO ]', 'cyan'), 'name : ', p['name'])
                        cursor.execute(get_latest_version(), (p['choco_id'],))  
                        latest = cursor.fetchone()
                        if (latest is None):
                            print(colored('[ INFO ]', 'cyan'), 'only this version {}'.format(p['version']))
                        else:
                            print(colored('[ INFO ]', 'cyan'), 'from version {} to {}'.format(latest['version'], p['version']))
                        print(colored('[ INFO ]', 'cyan'), 'description : ', p['description'])
                        print(colored('[ INFO ]', 'cyan'), 'fetch @', p['fetch_timestamp'], '\n')
        except sqlite3.Error as e:
            if(debug): print(colored('[ ERROR ]', 'magenta'), 'SQL (create_db_struct) : ')
            print(e)
            errors += 1
            msg = msg + '\n' + ('Error in SQL (create_db_struct) {}').format(e)

def choco_core_feeder():
    # ===== BEGIN ===== core feeder ===== 
    global errors
    global warns
    global subject
    global msg
    msg = ''
    subject = '[ DONE ] Choco check_updates'
    if(debug): print(colored(':::::::::::::::::::::::::::::::::::::::::::::: DEBUG MODE ENABLED ::::::::::::::::::::::::::::::::::::::::::::::::::::::::', 'yellow'))
    if(debug): print(colored('[ INFO ]', 'cyan'), 'Connecting to SQL')
    total = 0
    already_in = 0
    pending = 0
    warns = 0
    errors = 0
    conn = None
    try: 
        conn = db_connect(db_path)
        #cursor = conn.cursor(dictionary=True, buffered=True)
        cursor = conn.cursor()
        cursor.execute(get_package_data())    
        packages = cursor.fetchall()
        # 0 : id
        # 1 : name
        # -1 : choco_id
        # packages = [dict(zip(cursor.column_names, row)) for row in packages] # list comprehension, map query to dict
        packages = [dict(row) for row in packages]
        for p in packages:
            total += 1
            url = choco_community_pkg.format(p['choco_id'])
            if(debug):
                print()
                print(colored('[ INFO ]', 'cyan'), 'Package : ', p)
                print(colored('[ INFO ]', 'cyan'), 'Fetch url : ', url) 
            response = requests.get(url)
            data = xml2dict(response.content)
            if (len(data.keys()) > 0):
                if(data['islatestversion'].lower() == 'true' and data['isprerelease'].lower() == 'false' and data['isapproved'].lower() == 'true' and data['packagestatus'].lower() == 'approved'):
                    cursor.execute(get_update_data(), (p['id'], data['version']))
                    #if(cursor.rowcount <= 0):
                    temp = cursor.fetchone()
                    if(temp is None):
                        if(debug): print(colored('[ INFO ]', 'cyan'), ('No update found in my repo for {}, version {}').format(p['name'], data['version'])) # no update found in uniurb repo 
                        # update previous pending version to skipped
                        cursor.execute(set_skip_package(), (p['id'],)) 
                        cursor.execute(insert_pending_update(), (p['id'], data['version'], datetime.datetime.now()))
                        conn.commit()
                        pending += cursor.rowcount
                        if(cursor.rowcount <= 0): 
                            errors += 1
                            print(colored('[ ERROR ]', 'magenta'), end=' ')
                            cursor.execute(get_package_data(1), (data['id'],))
                        else:
                            if(debug): 
                                print(colored('[ INFO ]', 'cyan'), end=' ')
                                print(('New Version detected:\n\tPackage {} \nVersion {} Insert : {}\n').format(p['name'], data['version'], cursor.rowcount))
                        #print('SQL Insert, affected rows : ', cursor.rowcount)
                        msg = msg + '\n❃' + ('Package {} \nVersion {} Insert new record : {}\n').format(p['name'], data['version'], cursor.rowcount)
                    else:
                        if(debug): print(colored('[ INFO ]', 'cyan'), ('An update was found in my repo:\n\t {}\n\t version {}.\n\t Status : {}').format(p['name'], data['version'], temp['sname']))
                        already_in += 1
                        if(temp['sname'] == 'pending'):
                            msg = msg + '\n❃'
                            pending += 1
                        elif(temp['sname'] == 'updated'):
                            msg = msg + '\n✔'
                        else:
                            msg = msg + '\n' 
                        msg = msg + ('Package {} \nVersion {} \nAlready in repo\nStatus : {}\n').format(p['name'], data['version'], temp['sname'])
                else:
                    if(debug): print(colored('[ WARN ]', 'yellow'), ('Package {} not safe to deploy').format(p['name']))
                    warns += 1
                    msg = msg + '\n' + ('✖Package {} not safe to deploy\n').format(p['name'])
        #cursor.close()
        #conn.close()
        print(colored('Completed!', 'cyan'), ('Packages in repo {}, already collected {}, new entry {}').format(total, already_in, pending))
        msg = msg + '\n' + ('Packages in repo {}, already collected {}, new entry {}').format(total, already_in, pending)
    except requests.exceptions.RequestException as e:
        if(debug): print(colored('[ ERROR ]', 'magenta'), 'HTTP Request : ')
        print(e)
        errors += 1
        msg = msg + '\n' + ('Error in HTTP Request {}').format(e)
    except sqlite3.Error as e:
            if(debug): print(colored('[ ERROR ]', 'magenta'), 'SQL (db_connect) : ')
            print(e)
            errors += 1
            msg = msg + '\n' + ('Error in SQL (db_connect) {}').format(e)
#    except mysql.connector.Error as e:
#        if(debug): print(colored('[ ERROR ]', 'magenta'), 'SQL connection : ')
#        print(e)
#        errors += 1
#        msg = msg + '\n' + ('Error in SQL connection {}').format(e)
    finally:
        #if(conn.is_connected()):
        if(conn is not None):
            cursor.close()
            conn.close()
            if(debug): print(colored('[ INFO ]', 'cyan'), 'SQL Connection closed. bye bye')
        if(pending > 0):
            subject = '[ NEWS ] Choco check_updates'
        if(warns > 0):
            subject = '[ WARN ] Choco check_updates' 
        if(errors > 0):
            subject = '[ FAIL ] Choco check_updates'
        event_trigger(1, subject, msg)
    # ===== END ===== core feeder =====

def cron_client_update():
    global errors
    #global warns
    global subject
    global msg
    subject = '[ DONE ] Choco client_update'
    msg = ''
    if(debug): print(colored(':::::::::::::::::::::::::::::::::::::::::::::: DEBUG MODE ENABLED ::::::::::::::::::::::::::::::::::::::::::::::::::::::::', 'yellow'))
    if(debug): print(colored('[ INFO ]', 'cyan'), 'Connecting to SQL')
    try: 
        conn = db_connect(db_path)
        #cursor = conn.cursor(dictionary=True, buffered=True)
        cursor = conn.cursor()
        cursor.execute(get_all_pending_updates())    
        packages = cursor.fetchall()
        packages = [dict(row) for row in packages]
        if(len(packages) == 0):
            msg = msg + '\n' + ('No packages marked for update.')
            if(debug): print(colored('[ INFO ]', 'cyan'), 'No packages marked for update.')
        else:
            for p in packages:
                if(debug): print(colored('[ INFO ]', 'cyan'), 'Package : ', p)
                #subprocess.call('C:\Windows\System32\powershell.exe TODO::UPGRADE '+p['choco_id'], shell=True)
                cursor.execute(set_update_package(), (datetime.datetime.now(), p['package_id'], p['version'], ))
                msg = msg + '\n' + ('Update package {} to version {}\n').format(p['name'], p['version'])
                dw = temp_folder + folder_separator + p['choco_id'] + pkg_extension
                if(debug) : print(colored('[ INFO ]', 'cyan'), 'Download path', dw)
                event_trigger(0, '', '', 'mkdir {} && powershell.exe Invoke-WebRequest {} -OutFile {}'.format(temp_folder, choco_community_download.format(p['choco_id'], p['version']), dw))
                event_trigger(0, '', '',"powershell.exe choco push {} --source=\"'{}'\" -y -k=\"'{}'\"".format(dw, choco_local, choco_local_push_key))
                # NOTE :: maybe a fast folder creation / deletion could trigger antivirus, need to test
                event_trigger(0, '', '', 'rmdir /Q /S {}'.format(temp_folder))
                conn.commit()
        #cursor.close()
        #conn.close()
    except sqlite3.Error as e:
        if(debug): print(colored('[ ERROR ]', 'magenta'), 'SQL (db_connect) : ')
        print(e)
        errors += 1
        msg = msg + '\n' + ('Error in SQL (db_connect) {}').format(e)
#    except mysql.connector.Error as e:
#        if(debug): print(colored('[ ERROR ]', 'magenta'), 'SQL connection : ')
#        print(e)
#        errors += 1
#        msg = msg + '\n' + ('Error in SQL connection {}').format(e)
    finally:
        #if(conn.is_connected()):
        if(conn is not None):
            cursor.close()
            conn.close()
            if(debug): print(colored('[ INFO ]', 'cyan'), 'SQL Connection closed. bye bye')
        if(warns > 0):
            subject = '[ WARN ] Choco client_update' 
        if(errors > 0):
            subject = '[ FAIL ] Choco client_update'
        event_trigger(1, subject, msg)
# ===== END ===== functions =====

def main():
    global errors
    print(colored('Running script version', 'green'), version)
    if(len(sys.argv) == 1):
        print(colored('[ ERROR ]', 'magenta'), 'Argument needed (e.g. python xml-parser.py check_updates)')
        errors += 1
    else:
        funct = sys.argv[1]
        if(funct == 'check'):
            sync_repo_package(db_connect(db_path))
            choco_core_feeder()
        elif(funct == 'upgrade'):
            # call also check_updates?
            cron_client_update()
        elif(funct == 'status'):
            package_status_update(db_connect(db_path))
        elif(funct == 'init'):
            create_db_struct(db_connect(db_path))
        else:
            print(colored('[ ERROR ]', 'magenta'), 'Unrecognized mode ', funct)
            errors += 1
if (__name__ == '__main__'):
    main()


