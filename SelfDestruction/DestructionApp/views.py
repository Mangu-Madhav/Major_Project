from django.shortcuts import render
from django.template import RequestContext
from django.contrib import messages
from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage
import numpy as np
import base64
import os
from datetime import datetime
from hashlib import sha256
import pyaes, pbkdf2, binascii, secrets
import json
from web3 import Web3, HTTPProvider

import ecdsa
from hashlib import sha256
import pickle
import re
from datetime import date

global username, usersList, verify_list
global contract, web3

#function to call contract
def getContract():
    global contract, web3
    blockchain_address = 'http://127.0.0.1:9545/'
    web3 = Web3(HTTPProvider(blockchain_address))
    web3.eth.defaultAccount = web3.eth.accounts[0]
    compiled_contract_path = 'FileDestruction.json' #FileDestruction contract file
    deployed_contract_address = '0xC288A0776ae0b62951762B9546aF6b0Cc9A0AFcf' #contract address
    with open(compiled_contract_path) as file:
        contract_json = json.load(file)  # load contract info as JSON
        contract_abi = contract_json['abi']  # fetch contract's abi - necessary to call its functions
    file.close()
    contract = web3.eth.contract(address=deployed_contract_address, abi=contract_abi)
getContract()

def getUsersList():
    global usersList, contract
    usersList = []
    count = contract.functions.getUserCount().call()
    for i in range(0, count):
        user = contract.functions.getUsername(i).call()
        password = contract.functions.getPassword(i).call()
        phone = contract.functions.getPhone(i).call()
        email = contract.functions.getEmail(i).call()
        address = contract.functions.getAddress(i).call()
        usersList.append([user, password, phone, email, address])

def getVerifyList():
    global verify_list, contract
    verify_list = []
    count = contract.functions.getFileCount()().call()
    for i in range(0, count):
        owner = contract.functions.getOwner(i).call()
        filename = contract.functions.getFilename(i).call()
        filekey = contract.functions.getKey(i).call()
        destruct_date = contract.functions.getDestructionDate(i).call()
        verify_list.append([owner, filename, filekey, destruct_date])

getUsersList()
getVerifyList()

def getDestructionDate(date_str1, date_str2, date_format='%Y-%m-%d'):
    try:
        date1 = datetime.strptime(date_str1, date_format).date()
        date2 = datetime.strptime(date_str2, date_format).date()
    except ValueError:
        return "invalid"
    if date1 < date2:
        return "before"
    elif date1 > date2:
        return "after"
    else:
        return "same"

def generateKeys():
    secret_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1, hashfunc=sha256) # The default is sha1
    private_key = secret_key.get_verifying_key()
    private_key = private_key.to_string()[0:32]    
    return private_key

def encryptAES(plaintext, key): #AES data encryption
    aes = pyaes.AESModeOfOperationCTR(key, pyaes.Counter(31129547035000047302952433967654195398124239844566322884172163637846056248223))
    ciphertext = aes.encrypt(plaintext)
    return ciphertext

def decryptAES(enc, key): #AES data decryption
    aes = pyaes.AESModeOfOperationCTR(key, pyaes.Counter(31129547035000047302952433967654195398124239844566322884172163637846056248223))
    decrypted = aes.decrypt(enc)
    return decrypted

def UploadFileAction(request):
    if request.method == 'POST':
        global username
        global verify_list
        myfile = request.FILES['t1'].read()
        fname = request.FILES['t1'].name
        destruction = request.POST.get('t2', False)
        print(destruction)
        if os.path.exists("DestructionApp/static/files/"+fname):
            os.remove("DestructionApp/static/files/"+fname)
        key = generateKeys().decode("latin-1")
        file_encrypt = encryptAES(myfile, key.encode("latin-1"))
        with open("DestructionApp/static/files/"+fname, "wb") as file:
            file.write(file_encrypt)
        file.close()

        msg = contract.functions.saveFile(username, fname, key, destruction).transact()
        tx_receipt = web3.eth.waitForTransactionReceipt(msg)
        verify_list.append([username, fname, key, destruction])
        status = '<font size="3" color="blue">File Saved in Blockchain with encryption keys = '+str(key)+" & Destruction Date = "+str(destruction)+"</font><br/>"
        # status += str(tx_receipt)
        context= {'data':status}
        return render(request, 'UploadFile.html', context)

def Download(request):
    if request.method == 'GET':
        global verify_list
        index = request.GET.get('requester', False)
        vl = verify_list[int(index.strip())]
        name = vl[1]
        key = vl[2]
        key = key.encode("latin-1")
        with open("DestructionApp/static/files/"+name, "rb") as file:
            data = file.read()
        file.close()        
        aes_decrypt = decryptAES(data, key)
        response = HttpResponse(aes_decrypt,content_type='application/force-download')
        response['Content-Disposition'] = 'attachment; filename='+name
        return response

def checkDestruction(date_str2, date_format='%Y-%m-%d'):
    date_str1 = str(date.today())
    try:
        date1 = datetime.strptime(date_str1, date_format).date()
        date2 = datetime.strptime(date_str2, date_format).date()
    except ValueError:
        return "invalid"
    if date1 < date2:
        return "before"
    elif date1 > date2:
        return "after"
    else:
        return "same"    

def DownloadFile(request):
    if request.method == 'GET':
        global username, verify_list
        output = '<table border=1 align=center width=100%><tr><th><font size="3" color="black">Owner Name</th><th><font size="3" color="black">File Name</th>'
        output+='<th><font size="3" color="black">Decryption Key</th><th><font size="3" color="black">Destruction Date</th><th><font size="3" color="black">Download File</th></tr>'
        for i in range(len(verify_list)):
            vl = verify_list[i]
            destruction = checkDestruction(vl[3])
            print(destruction)
            output += '<tr><td><font size="" color="black">'+str(vl[0])+'</td><td><font size="" color="black">'+vl[1]+'</td>'
            output+='<td><font size="3" color="black">'+vl[2]+'</td><td><font size="3" color="black">'+vl[3]+'</td>'
            if destruction == "same" or destruction == "before":
                output +='<td><a href=\'Download?requester='+str(i)+'\'><font size=3 color=green>Download</font></a></td></tr>'
            else:
                output+='<td><font size="3" color="red">File Destructed & Not Available to Download</td></tr>'
        output += "</table><br/><br/><br/><br/>"    
        context= {'data':output}
        return render(request, 'UserScreen.html', context)

def UploadFile(request):
    if request.method == 'GET':
        return render(request, 'UploadFile.html', {})

def UserLogin(request):
    if request.method == 'GET':
        return render(request, 'UserLogin.html', {})

def index(request):
    if request.method == 'GET':
        return render(request, 'index.html', {})

def Register(request):
    if request.method == 'GET':
       return render(request, 'Register.html', {})

def RegisterAction(request):
    if request.method == 'POST':
        global usersList
        username = request.POST.get('t1', False)
        password = request.POST.get('t2', False)
        contact = request.POST.get('t3', False)
        email = request.POST.get('t4', False)
        address = request.POST.get('t5', False)
        count = contract.functions.getUserCount().call()
        status = "none"
        for i in range(0, count):
            user1 = contract.functions.getUsername(i).call()
            if username == user1:
                status = "exists"
                break
        if status == "none":
            msg = contract.functions.saveUser(username, password, contact, email, address).transact()
            tx_receipt = web3.eth.waitForTransactionReceipt(msg)
            usersList.append([username, password, contact, email, address])
            context= {'data':'<font size="3" color="blue">Signup Process Completed</font><br/>'}
            print(tx_receipt)
            return render(request, 'Register.html', context)
        else:
            context= {'data':'Given username already exists'}
            return render(request, 'Register.html', context)

def UserLoginAction(request):
    if request.method == 'POST':
        global username, contract, usersList
        username = request.POST.get('username', False)
        password = request.POST.get('password', False)
        status = 'none'
        for i in range(len(usersList)):
            ulist = usersList[i]
            user1 = ulist[0]
            pass1 = ulist[1]            
            if user1 == username and pass1 == password:
                status = "success"
                break
        if status == 'success':
            output = 'Welcome '+username
            context= {'data':output}
            return render(request, "UserScreen.html", context)
        if status == 'none':
            context= {'data':'Invalid login details'}
            return render(request, 'UserLogin.html', context)

