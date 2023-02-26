import asyncio
import websockets 
import json
from twilio.rest import Client
import math
from web3 import Web3
from ens import ENS

AMBERDATA_API_KEY = 'API KEY '
url = f'wss://ws.web3api.io?x-api-key={AMBERDATA_API_KEY}'
account_sid = 'TWILIO ID'
auth_token = 'TWILIO AUTH TOKEN'
transfer_max = 1000000 #Watching transfers of tokens above this amount. 
amberdata_rpc_url = f'https://rpc.web3api.io/api/v2?x-api-key={AMBERDATA_API_KEY}'

async def handler(websocket):
    client = Client(account_sid, auth_token)
    w3 = Web3(Web3.HTTPProvider(amberdata_rpc_url))
    ns = ENS.from_web3(w3)
    message = '{"jsonrpc" : "2.0","id": 1, "method"  : "subscribe", "params"  : ["addresses:logs",{ "address": "0x6b175474e89094c44da98b954eedeac495271d0f" }]}'
    while True:
        await websocket.send(message)
        message = await websocket.recv()
        if(message == '''Could not parse JSON Request, type 'help' for more details.''' or message == '''Improper Format: id must be string|number|not provided''' or message == '''Improper Format: provide method string'''):
            pass
        else:
            data = json.loads(message)
            if ('params' in data):
                transfer_value = round(float.fromhex(data['params']['result']['data'])/ math.pow(10, 18), 2)

                
                from_address =  '0x'+ data['params']['result']['topics'][1][26:]
                to_address =  '0x'+ data['params']['result']['topics'][2][26:]
                topic = data['params']['result']['topics'][0]

                if transfer_value > transfer_max and topic == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef': 
                    print(to_address, from_address, transfer_value, data['params']['result']['transactionHash'])

                    client.messages.create(body=f'{transfer_value} DAI was transferred {from_address} to {to_address}', from_ =  +"YOUR TWILO PROVIDED NUMBER HERE",to = +"YOUR CELL PHONE NUMBER HERE")
            else:
                pass


async def main():
    async with websockets.connect(url) as ws:
        await handler(ws)
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    print("started")
    asyncio.run(main())
