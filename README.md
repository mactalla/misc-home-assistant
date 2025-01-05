## Matter binding in Home Assistant

### Expose the WebSocket port of the Matter Add-On

Navigate to Add-Ons -> Matter Server -> Config -> Network

Enter `5580`

Close it back up when you're done.  You don't really want to leave it open on your network.

### Run the binding script

`pip3 install websocket-client` if you don't have it already

For each pair of devices to bind:
* Find each Node ID from Settings -> Devices -> (device you want) -> Device Info -> Node ID
* Run ./matter-binding.py --from (source node) --to (dest node)
  * For endpoints other than 1, specify it with `:#`.  eg: Inovelli switches have the Dimmer Switch that we can bind on Endpoint 2
    `./matter-binding.py --from 17:2 --to 21`

### Limitations

While this script Works For Me and does attempt to be smart about updates (no changes if none are needed, re-use a suitable entry in the ACL or binding tables).
It still has notable limitations:
* It has been tested only superficially.
* It does not support un-binding.
* It binds "everything" (ie: any matching command that the source can issue and the receiver will acknowledge will be found).
  * There is no support for binding only a subset.
* Use at your own risk, yadda yadda.

### Future

Home Assistant has plans to add support for Binding in the future.  Once that exists, this script should just be deleted and forgotten.  It has no future :)
