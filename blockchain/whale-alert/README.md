# Websocket Whale Tranfers Alerts 

This example will allow you to connect to the Amberdata Blockchain Event websocket feed.  We will consume raw event data from the `DAI` contract address. 
Then we will filter for only `Transfer` events over $1,000,000. 

Additionally, we will check the wallets transfers for ENS domains to contextualize the tranfer.  

When the event is observed, we will then use `Twilio` API to text ourselves when this occurs. 

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install this repos dependencies.

```bash
pip install -r requirements.txt
```

Twilio: [Twilio API Setup](https://www.twilio.com/login).  
    1. Create an account on Twilio. 
    2. Verify the phone number you'd like to receive alerts. 
    3. Copy your Account SID & your Auth Token (🔒 don't share your auth token 	🔒)
    4. Click "Get A Trial Number". 

## Usage

```python
python3 whale-alerty.py
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)