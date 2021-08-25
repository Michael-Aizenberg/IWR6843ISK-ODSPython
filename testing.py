import struct
import numpy as np
place_values = []
for i in range(31,-1,-1):
    place_values.append(2**i)


place_values_frac = []

for i in range(1,32):
    place_values_frac.append(2**(-i))


def bytesToDecimal(bytes):
    combined = ""
    if type(bytes) == list:
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
    if type(bytes) == list:
        for byte in bytes[::-1]:
            byteInBin = np.binary_repr(byte)
            for i in range(8-len(byteInBin)):
                byteInBin = '0' + byteInBin
           
            combined = combined + byteInBin

        bits = [int(x) for x in combined]
        
    sign = bits[0]
    
    exponent = np.matmul(bits[1:9], [128,64,32,16,8,4,2,1]) -127


    mantissa = bits[9:]
    mantissa = [1,"."] + mantissa
    print(mantissa)

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

    return finalFloat
    


print(bytesToFloat([103, 182, 102, 62]))
print(bytesToFloat([169, 89, 130, 62]))

