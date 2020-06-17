from Crypto.Cipher import AES
import base64

BS = AES.block_size
pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
unpad = lambda s : s[0:-ord(s[-1])]

def aes_encode(key,text):
    cipher = AES.new(key)
    encrypted = cipher.encrypt(pad(text))
    result = base64.b64encode(encrypted)
    return result

def aes_decode(key,result):
    cipher = AES.new(key)
    result2 = base64.b64decode(result)
    decrypted = unpad(cipher.decrypt(result2))
    return decrypted

