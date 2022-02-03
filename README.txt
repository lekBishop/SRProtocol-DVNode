PA2 README
CSEE 4119 Computer Networks

Emulates selective repeat protocol over udp and the distance-vector algorithm as well as both combined.

All of the programs check for valid port numbers and probabilities of dropping are expected [0,1]

Selective Repeat:
	Command Line:
	- Same as those shown in the PA2 assignment
	- Run chmod to turn .py to executable
		- chmod +x srnode.py
	- Run program:  ./srnode <self-port> <peer-port> <window-size> [ -d <value-of-n> j -p <value-of-p>]
	Client Command:
	- send a message to peer: send <message>

	Description: 
	The program works as intended, emulating the selective repeat protocol by breaking up the user string sent into separate chars and sending them. The program uses two threads one for recieving and one for sending. They both share a global sender window implemented using a python dictionary. The packet timeouts are kept track in an array and resent if they timeout.

	Problems:
	Sometime if the last ACK is dropped the reciever will have finished recieving, but the sender sends another packet. This causes the reciever to start again thinking its a new message. I tried to fix it by waiting a bit after the last ACK is sent, but the issue still occurs occaisionally.


Distance-Vector Routing Algorithm:
	Command Line:
	- ./dvnode <local-port> <neighbor1-port> <loss-rate-1> <neighbor2-port> <loss-rate-2> ... [last]

	Description:
	For the dvnode program, I went with the non-threaded message as I found I was able to parse through the routing tables quick enough to not drop any packets on the recieve buffer. The program works by first waiting to recieve a table. The program running with the "last" parameter sends the first table to its neighbors. Once a table is recieved, the DV algorithm is run on it and then if any changes are made or its the first time the node recieved a table, it will forward it's table to the neighbors. I used a dictionary to format the routing table for each node and used JSON to serialize the tables to easily send them as strings over udp to be rebuilt at the other end. The nodes also keep track of the latest tables, so it ignores any old tables that might have gotten sent out of order.


Combination:
	Command Line:
	./cnnode <local-port> receive <neighbor1-port> <loss-rate-1> <neighbor2-port> <loss-rate-2> ... <neighborM-port>
	<loss-rate-M> send <neighbor(M+1)-port> <neighbor(M+2)-port> ... <neighborN-port> [last]

	Description:
	The program consists of three threads running. The sender thread sends probe packets about every 10ms, routing_tables every 5s and displays the current drop rate for all "send" ports every 1s. The reciever thread handles recieving probe packets, sending ACKs, and parsing routing_tables. Lastly, the timeout thread is created everytime a packet is sent and waits 500ms before checking if the packet is still in the window, if so it will send another packet and wait again, this also tracks the number of dropped packets.When the node with the "last" argument is started, it sends a routing table to its neighbors signaling them to start sending probe packets. As the probe packets are sent, the sender nodes determine the send rate from the amount of dropped packets and get an idea of their direct link costs. These values are then sent through routing_tables to other nodes. After a while, the routing tables will all have the lowest costs for sending packets from themselves to all other nodes on the network.

	Problems:
	Sometimes it seems to take a while for the values to converge on the routing tables even though the values from the nodes themselves are accurate to the values from the command line. I'm not sure if this is an issue or not, but it does happen.
	
