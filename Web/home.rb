require 'sinatra'
require 'json'
require 'open3'

set :port, '8181'
set :bind, '0.0.0.0'

get '/' do
        File.read('home.html')

end




post '/add-server' do

        params = JSON.parse(request.env["rack.input"].read)
#       puts params.inspect
        data =  {:server => "", :username => "", :password => ""}

        params.each {|element|
                case element['name']
                        when 'servername' then data[:server] = element['value']
                        when 'user' then data[:username] = element['value']
                        when 'password' then data[:password] = element['value']
                        else puts "errore"
                end
        }
        cmd = 'python /opt/CentralConsole/Script/System/insert-credential.py '+ data[:server] + ' ' + data[:username] + ' ' + data[:password]
        Open3.popen3(cmd) do | stdin, stdout, stderr, status, thread, wait_thr|
                x = stdout.read
                if x.include? "990"
                        {:time => Time.now, :result => "User Already Exist"}.to_json
                elsif x.include? "0"
                        {:time => Time.now, :result => "New User Added" }.to_json
                else
                        {:time => Time.now, :result => "Generic Error" }.to_json
                end
        end

end

post '/backup-vm' do

        params = JSON.parse(request.env["rack.input"].read)
        puts params.inspect
        data =  {:server => "", :username => "", :vmname => ""}

        params.each {|element|
                case element['name']
                        when 'servername' then data[:server] = element['value']
                        when 'user' then data[:username] = element['value']
                        when 'vmname' then data[:vmname] = element['value']
                        else puts "errore"
                end
        }
        puts "-----------------"
        puts data[:server]
        puts data[:username]
        puts data[:vmname]
        puts "-----------------"
        cmd = 'python /opt/CentralConsole/Script/VMWare/backup.py '+ data[:server] + ' ' + data[:username] + ' ' + data[:vmname]
        Open3.popen3(cmd) do | stdin, stdout, stderr, status, thread, wait_thr|
                x = stdout.read
                y = stderr.read
                puts x
                puts y
                if x.include? "990"
                        {:time => Time.now, :result => "Error During Backup"}.to_json
                elsif x.include? "0"
                        {:time => Time.now, :result => "Backup Completed Succefully" }.to_json
                else
                        {:time => Time.now, :result => "Generic Error" }.to_json
                end
        end

end
