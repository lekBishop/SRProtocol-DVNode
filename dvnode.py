#! /usr/bin/python3

import sys
import socket
import time
import json
import re

localhost = "127.0.0.1"

class Node:

    # Initialize the node with routing table and list of neighbors, also bind the socket
    def __init__(self, port, argv):
        self.neighbors = {}
        self.routing_table = {}
        self.port = port
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind((localhost, self.port))
        except socket.error as e:
            print("Socket Error: {}".format(e))
            sys.exit()
        
        self.routing_table[self.port] = [0, 0]
        self.neighbors[self.port] = [0, 0]
        self.initial_send = True

        i = 0
        while i < len(argv):
            port = int(argv[i])
            loss_rate = float(argv[i+1])
            if 1024 <= port <= 65535 and 0 < loss_rate < 1:
                self.neighbors[port] = [loss_rate, 0]
                self.routing_table[port] = [loss_rate]
                self.routing_table[port].append(0)
                i += 2
            else:
                print("Port number range: [1024, 65535]")
                print("Loss-rate range: (0,1)")
                sys.exit()

    # Prints the routing table
    def print_table(self):
        print("[{}] Node {} Routing Table".format(time.time(), self.port))
        for node, value in self.routing_table.items():
            if value[0] != 0:
                print("- ({}) -> Node {}".format(value[0], node),end="")
                if value[1] > 0:
                    print("; Next Hop -> Node {}".format(value[1]))
                else:
                    print()

    # Sends the current routing table to all neighbors
    def send_neighbors(self):
        serialized_table = json.dumps(self.routing_table) + " " + str(time.time())
        for port in self.neighbors.keys():
            if port != self.port:
                self.sock.sendto(serialized_table.encode("utf-8"), (localhost, port))

    # Given a neighbors routing table and port, update current routing table if necessary
    def parse_table(self, recieved_table, sender_port):
        recieved_table = json.loads(recieved_table)
        notify_neighbors = False
        for key, data in recieved_table.items():
            new_cost = round(self.neighbors[sender_port][0] + data[0],2)
            port = int(key)
            if not(port in self.routing_table.keys()) or new_cost < self.routing_table[port][0]:
                self.routing_table[port] = [new_cost, sender_port]
                notify_neighbors = True

        if notify_neighbors or self.initial_send:
            self.print_table()
            self.initial_send = False
            self.send_neighbors()

    def newest_table(self, new_timestamp, port):
        if new_timestamp > self.neighbors[port][1]:
            self.neighbors[port][1] = new_timestamp
            return True
        return False
         
def main(argv):
    args = len(argv)

    if args > 2:
        
        last = argv[-1] == "last"
        if last:
            argv.pop()

        self_port = int(argv.pop(0))
        if not 1024 <= self_port <= 65535:
            print("Port number must be between 1024 and 65535")
            sys.exit()

        if len(argv)%2 != 0:
            print("Must include a weight for each port")
            sys.exit()


        node = Node(self_port, argv)
        node.print_table()

        # Last node begins the algorithm
        if last:
            node.send_neighbors()

        buf = 4096

        while True:
            data, addr = node.sock.recvfrom(buf)
            new_timestamp = float(data.decode("utf-8").split().pop())
            
            if node.newest_table(new_timestamp, addr[1]):
                node.parse_table(re.search('{.*}',data.decode("utf-8")).group(0), addr[1])

    else:
        print("Usage: dvnode <local-port> <neighbor1-port> <loss-rate-1> <neighbor2-port> <loss-rate-2> ... [last]")

if __name__=='__main__':
    main(sys.argv[1:])
