#! /bin/bash

[ -r /etc/default/cc-webhome ] && . /etc/default/cc-webhome

cd /opt/CentralConsole/Script/Web

/opt/CentralConsole/jruby/bin/jruby home.rb >> /var/log/CentralConsole/WebService.log 2>&1

