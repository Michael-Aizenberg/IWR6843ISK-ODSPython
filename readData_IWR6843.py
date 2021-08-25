import serial
import json
import time
import numpy as np
import PyQt5
import struct
from pyqtgraph.Qt import QtGui
import pyqtgraph as pg
import pandas as pd
import openpyxl as op

#This is not important, it was for combining bytes but it was much easier in C
place_values = []
for i in range(31,-1,-1):
    place_values.append(2**i)

place_values_frac = []
for i in range(1,32):
    place_values_frac.append(2**(-i))


#for excel
rownum = 2

configFileName = 'ODS_6m_default.cfg'


#for excel but I didn't want it running when just testing
#workbook = op.load_workbook('mmwRawData.xlsx')
#print(workbook.sheetnames)

#emptyRoomSheet = workbook['EmptyRoom']
#onePersonSheet = workbook['OnePerson']
#twoPersonSheet = workbook['TwoPeople']


#initializing ports, bytebuffer is something I didn't use
CLIport = {}
Dataport = {}
#byteBuffer = np.zeros(2**15,dtype = 'uint8')
byteBufferLength = 0;



# ------------------------------------------------------------------
#function to convert bytes to decimal
def bytesToDecimal(bytes):
    combined = ""
    if type(bytes.tolist()) == list:
        for byte in bytes[::-1]:
            byteInBin = np.binary_repr(byte)
            for i in range(8-len(byteInBin)):
                byteInBin = '0' + byteInBin
           
            combined = combined + byteInBin

        bits = [int(x) for x in combined]


        try:
            dec = np.matmul(bits, place_values[len(place_values)-len(bits):32])
            return dec
        except:
            print(bits)
            return np.matmul([0,0],[0,0])
        
    else:
        return bytes
def bytesToFloat(bytes):
    combined = ""
    if type(bytes.tolist()) == list:
        for byte in bytes[::-1]:
            byteInBin = np.binary_repr(byte)
            for i in range(8-len(byteInBin)):
                byteInBin = '0' + byteInBin
           
            combined = combined + byteInBin

        bits = [int(x) for x in combined]

    try:
        sign = bits[0]
    
        exponent = np.matmul(bits[1:9], [128,64,32,16,8,4,2,1]) -127


        mantissa = bits[9:]
        mantissa = [1,"."] + mantissa


        if exponent < 0:
            for i in range(abs(exponent)-1):
       
                if i == 0:
                    mantissa[1] = 1
                    mantissa[0] = "."
                if i >= 0:
                    mantissa.insert(1,0)

        elif exponent > 0:
            mantissa.pop(1)
            mantissa.insert(exponent+1,".")

        beforePoint = mantissa[:mantissa.index(".")]
        afterPoint = mantissa[mantissa.index(".")+1:]

        beforePointDec = np.matmul(beforePoint, place_values[len(place_values)-len(beforePoint):32])
        afterPointDec = np.matmul(afterPoint,place_values_frac[:len(afterPoint)])
    
        finalFloat = beforePointDec + afterPointDec
    except:
        finalFloat = 0
        pass

    return finalFloat
# Function to configure the serial ports and send the data from
# the configuration file to the radar
def serialConfig(configFileName):
    
    global CLIport
    global Dataport
    # Open the serial ports for the configuration and the data ports
    
    # Raspberry pi
    #CLIport = serial.Serial('/dev/ttyACM0', 115200)
    #Dataport = serial.Serial('/dev/ttyACM1', 921600)
    
    # Windows
    CLIport = serial.Serial('COM3', 115200)
    Dataport = serial.Serial('COM4', 115200)

    # Read the configuration file and send it to the board
    config = [line.rstrip('\r\n') for line in open(configFileName)]
    for i in config:
        CLIport.write((i+'\n').encode())
        print(i)
        time.sleep(0.01)
        
    return CLIport, Dataport

# ------------------------------------------------------------------


# Function to parse the data inside the configuration file
#I think this function is also unnessecary
def parseConfigFile(configFileName):
    configParameters = {} # Initialize an empty dictionary to store the configuration parameters
    
    # Read the configuration file and send it to the board
    config = [line.rstrip('\r\n') for line in open(configFileName)]
    for i in config:
        
        # Split the line
        splitWords = i.split(" ")
        
        # Hard code the number of antennas, change if other configuration is used
        numRxAnt = 4
        numTxAnt = 3
        
        # Get the information about the profile configuration
        if "profileCfg" in splitWords[0]:
            startFreq = int(float(splitWords[2]))
            idleTime = int(float(splitWords[3]))
            rampEndTime = float(splitWords[5])
            freqSlopeConst = float(splitWords[8])
            numAdcSamples = int(splitWords[10])
            numAdcSamplesRoundTo2 = 1;
            
            while numAdcSamples > numAdcSamplesRoundTo2:
                numAdcSamplesRoundTo2 = numAdcSamplesRoundTo2 * 2;
                
            digOutSampleRate = int(float(splitWords[11]));
            
        # Get the information about the frame configuration    
        elif "frameCfg" in splitWords[0]:
            
            chirpStartIdx = int(splitWords[1]);
            chirpEndIdx = int(splitWords[2]);
            numLoops = int(splitWords[3]);
            numFrames = int(splitWords[4]);
            framePeriodicity = int(float(splitWords[5]));

            
    # Combine the read data to obtain the configuration parameters           
    numChirpsPerFrame = (chirpEndIdx - chirpStartIdx + 1) * numLoops
    configParameters["numDopplerBins"] = numChirpsPerFrame / numTxAnt
    configParameters["numRangeBins"] = numAdcSamplesRoundTo2
    configParameters["rangeResolutionMeters"] = (3e8 * digOutSampleRate * 1e3) / (2 * freqSlopeConst * 1e12 * numAdcSamples)
    configParameters["rangeIdxToMeters"] = (3e8 * digOutSampleRate * 1e3) / (2 * freqSlopeConst * 1e12 * configParameters["numRangeBins"])
    configParameters["dopplerResolutionMps"] = 3e8 / (2 * startFreq * 1e9 * (idleTime + rampEndTime) * 1e-6 * configParameters["numDopplerBins"] * numTxAnt)
    configParameters["maxRange"] = (300 * 0.9 * digOutSampleRate)/(2 * freqSlopeConst * 1e3)
    configParameters["maxVelocity"] = 3e8 / (4 * startFreq * 1e9 * (idleTime + rampEndTime) * 1e-6 * numTxAnt)
    
    return configParameters
   
# ------------------------------------------------------------------

# Funtion to read and parse the incoming data
def readAndParseData14xx(Dataport, configParameters):
    global byteBuffer, byteBufferLength, frame
 
    magicWord = [2, 1, 4, 3, 6, 5, 8, 7]
    numOfPeople = 0
    xPos = 0
    
    # Initialize variables

    #This reads the data from the sensor and converts it to uint8
    readBuffer = Dataport.read(Dataport.in_waiting)
    byteVec = np.frombuffer(readBuffer, dtype = 'uint8')
    byteCount = len(byteVec)
    print(byteVec)


    #This is the code I tried that would find the number of people and just skipping through all the unnessecary bytes
    #The pointcloud tlv length would always be in the same spot (assuming the sensor detects some points) and then you can use that to find where the tlv length is 
    #To find the number of people from the targetlistTLVLength, just subtract 8 and divide by 112. This works because the target list tlv length = tlv header + (bytesPerTarget)*(numberOfTargets). The bytes per target = 112 and the header = 8

    #try:
        #pointCloudTLVLength = bytesToDecimal(byteVec[52:56])
        #targetListTLVlength = bytesToDecimal(byteVec[52 + pointCloudTLVLength:56 + pointCloudTLVLength])
       # print(targetListTLVlength)
    #except:
        #pass

   





    if byteCount>48:

        letters = ['A','B','C','D','E','F','G','H','I','J','K','L','M',"N","O",'P','Q','R','S','T','U','V',]
        
        # Initialize the pointer index
        idX = 0
        col =0 


        
        
        # Read the header
   
        
        magicNumber = byteVec[idX:idX+8]
        idX += 8


        
        version = byteVec[idX:idX+4]
        idX += 4

        totalPacketLen = byteVec[idX:idX+4]
        idX += 4



        platform = byteVec[idX:idX+4]
        idX += 4    

 

        frameNumber = byteVec[idX:idX+4]    
        idX += 4
 
  

        subframenum = byteVec[idX:idX+4]
        idX+=4



        chirpMargin = byteVec[idX:idX+4]
      
        idX+=4
     


        frameMargin = byteVec[idX:idX+4]
        idX+=4


        trackProcessTime = byteVec[idX:idX+4]
        idX+=4

        uartsenttime = byteVec[idX:idX+4]
        idX+=4
      




        

        numTLVs = byteVec[idX:idX+2]
        idX +=2
     

        checksum = byteVec[idX:idX+2]
        idX+=2

        #add header to dictionary, this was just for excel
        byteVecDict = {
         "magicNumber": magicNumber,
          'version' : bytesToDecimal(version),
          'totalPacketLen':bytesToDecimal(totalPacketLen),
          'platform':bytesToDecimal(platform),
          'frameNumber':bytesToDecimal(frameNumber),
          'subframenum': bytesToDecimal(subframenum),
          'chirpMargin': bytesToDecimal(chirpMargin),
          'frameMargin': bytesToDecimal(frameMargin),
          'trackprocesstime': bytesToDecimal(trackProcessTime),
          'uartsenttime': bytesToDecimal(uartsenttime),
          'numTLVs': bytesToDecimal(numTLVs),
          'checksum': bytesToDecimal(checksum),

                       
                       
        }

        #This part goes through all of the tlvs (point-cloud, target index, and the last one which isn't useful) in the frame and adds them to the dictionary.
        #This was mostly for excel since the only important tlv is the target list tlv. So it's probably much easier to just use the logic in the try statement above
        #a tlv_type of 7 means target list tlv 

        #I think numTLVs will always either be 1 or 3 but I decided to be safe with the if statement
        if bytesToDecimal(numTLVs) >= 1 and bytesToDecimal(numTLVs) < 10:

            for tlv in range(bytesToDecimal(numTLVs)):
                tlv_type = bytesToDecimal(byteVec[int(idX):int(idX+4)])
                idX += 4
     
                tlv_length = bytesToDecimal(byteVec[int(idX):int(idX+4)])
                idX += 4


                payload = byteVec[int(idX):int(idX)+int(tlv_length)-8]
                idX+=tlv_length-8
                

                byteVecDict.update({"tlv_type" + str(tlv+1): tlv_type})
                byteVecDict.update({"tlv_length" + str(tlv+1): tlv_length})
                byteVecDict.update({"payload" + str(tlv+1): payload})

                if tlv_type == 7:
                    numOfPeople = (tlv_length - 8)/112
        
                    


 #this was for excel
        #for key in byteVecDict:
          #  try:
           #     twoPersonSheet[letters[col] + str(rownum)] = json.dumps(byteVecDict[key].tolist())  
           # except:
           #     pass

            col+=1

        



        

        
       

    


    #print("xPos: " + str(xPos))
    #print("numOfPeople: " + str(numOfPeople))
    return numOfPeople

# ------------------------------------------------------------------


# ------------------------------------------------------------------


# ------------------------------------------------------------------

# I did not use this function
def update():
     
    dataOk = 0
    global detObj
    x = []
    y = []
      
    # Read and parse the received data
    dataOk, frameNumber, detObj = readAndParseData14xx(Dataport, configParameters)
    
    if dataOk and len(detObj["x"]) > 0:
        #print(detObj)
        x = -detObj["x"]
        y = detObj["y"]
        
        s.setData(x,y)
        QtGui.QApplication.processEvents()
    
    return dataOk


# -------------------------    MAIN   -----------------------------------------  

# Configurate the serial port
CLIport, Dataport = serialConfig(configFileName)

# Get the configuration parameters from the configuration file
configParameters = parseConfigFile(configFileName)

# START QtAPPfor the plot

    
   
# Main loop 
detObj = {}  
frameData = {}    
currentIndex = 0

while True:
    try:
        # Update the data and check if the data is okay
        readAndParseData14xx(Dataport,configParameters)
        rownum+=1
        time.sleep(0.033) # Sampling frequency of 30 Hz
        
        
    # Stop the program and close everything if Ctrl + c is pressed
    except KeyboardInterrupt:
        CLIport.write(('sensorStop\n').encode())
        CLIport.close()
        Dataport.close()
        win.close()
        break


    

#workbook.save('mmwRawData.xlsx')



