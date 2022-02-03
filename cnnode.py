#! /usr/bin/python3

import sys
import socket
import time
import threading
import random
import json
import re


localhost = "127.0.0.1"
sender_windows = {}
node = None

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

        self.routing_table[self.port] = [0.0, 0]
        self.neighbors[self.port] = 0
        self.initial_send = True

        i = 0
        while i < len(argv):
            port = int(argv[i])
            loss_rate = float(argv[i+1])
            if 1024 <= port <= 65535 and 0 <= loss_rate < 1:
                self.neighbors[port] = loss_rate
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
            if value[0] != self.port:
                print("- ({}) -> Node {}".format(round(value[0],2), node),end="")
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
        for key, data in recieved_table.items():
            cost = float(data[0])
            port = int(key)

            if not port in self.routing_table.keys():
                self.routing_table[port] = [cost, sender_port]
            if port == self.port:
                self.neighbors[sender_port] = cost
            current_cost = self.routing_table[port][0]
            cost_to_node = self.neighbors[sender_port]
            new_cost = round(cost_to_node + cost,2)

            if current_cost > new_cost or current_cost == 0 and port != self.port:
                if port == sender_port:
                    self.routing_table[port] = [new_cost, 0]
                else:
                    self.routing_table[port] = [new_cost, sender_port]
            elif sender_port ==  self.routing_table[port][1]:
                self.routing_table[port][0] = self.neighbors[sender_port] + cost

def not_lost(p):
    chance = random.randint(0,100)
    return  p*100 < chance

def valid_port(port_number):
    if not (1024 <= port_number <= 65535):
        print("Invalid port number")
        sys.exit()

def packet_timeout(sequence, port, sock, lock):
    global sender_windows

    time.sleep(0.5)
    if sequence in sender_windows[port][0]:
        lock.acquire()
        sender_windows[port][3] += 1
        lock.release()
        #print("packet {} timeout on port {}".format(sequence, port))
        while sequence in sender_windows[port][0]:
            msg = "probe|" + str(port) + "|" + str(sequence)
            sock.sendto(msg.encode("utf-8"), (localhost, port))
            time.sleep(0.5)

def send_packet(sock, lock):
    global sender_windows
    global node
    window_size = 5

    last_send = time.time()
    last_print = time.time()
    while True:
        if last_send + 5 < time.time():
            node.send_neighbors()
            node.print_table()
            last_send = time.time()
        for port in sender_windows.keys():
            if len(sender_windows[port][0]) < 5:
                lock.acquire()
                sequence = sender_windows[port][1]
                sender_windows[port][0].append(sequence)
                sender_windows[port][1] += 1

                msg = "probe|"+ str(port) + "|" + str(sequence)
                sender_windows[port][2] += 1
                lock.release()
                sock.sendto(msg.encode("utf-8"), (localhost, port))
                #print("send probe|{}|{}".format(port,sequence))

                timeout = threading.Thread(target=packet_timeout, args=(sequence, port, sock, lock))
                timeout.start()
                time.sleep(0.01)
            lock.acquire()
            total = float(sender_windows[port][2])
            lost = sender_windows[port][3]
            lock.release()
            node.neighbors[port] = lost/total
            if last_print + 1 < time.time():
                print("[{}] Link to {}: {} packets sent, {} packets lost, loss rate {}".format(time.time(), port, 
                total, lost, round(lost/total,2) ))
                last_print = time.time()

def recv_packet(sock, recv_neighbors, lock):
    buf = 4096
    global sender_windows
    global node

    while True:
        data, addr = sock.recvfrom(buf)
        packet = data.decode("utf-8").split("|")

        if packet[0] == "probe":

            #chance of being accepted
            #print("Recieved probe {} from port {}".format(packet[2], packet[1]))
            ack = "ACK|" + packet[1] + "|" + packet[2]
            prob = recv_neighbors[addr[1]]
            if not_lost(prob): 
                sock.sendto(ack.encode("utf-8"), addr)

        elif packet[0] == "ACK":
            port = int(packet[1])
            sequence = int(packet[2])
            #print("Recieved ACK {} from port {}".format(sequence, port))
            lock.acquire()
            if sequence in sender_windows[port][0]:
                sender_windows[port][0].remove(sequence)
            lock.release()
        else:
            node.parse_table(re.search('{.*}',data.decode("utf-8")).group(0), addr[1])

def main(argv):
    args = len(sys.argv)
    global sender_windows
    global node

    if args > 3:
        self_port = int(argv.pop(0))
        valid_port(self_port)

        if argv[0] != "recieve":
            print("must include recieve keyword")
            sys.exit()
        argv.pop(0)
        
        last = argv[-1] == "last"
        if last:
            argv.pop()

        node_list = []

        recv_neighbors = {}
        i = 0
        while argv[i] != "send":
            port = int(argv[i])
            valid_port(port)
            prob = float(argv[i+1])
            node_list.append(port)
            node_list.append(0)
            if not 0 <= prob <= 1:
                print("Probability range: [0,1]")
                sys.exit()
            recv_neighbors[port] = prob
            i += 2

        i += 1
        while i < len(argv):
            node_list.append(int(argv[i]))
            node_list.append(0)
            sender_windows[int(argv[i])] = [[], 0, 0, 0]            
            i += 1

        node = Node(self_port, node_list)
        node.print_table()

        if last:
            node.send_neighbors()

        buf = 4096
        data, addr = node.sock.recvfrom(buf)
        node.parse_table(re.search('{.*}',data.decode("utf-8")).group(0), addr[1])
        node.send_neighbors()

        lock = threading.Lock()
        sending = threading.Thread(target=send_packet, args=(node.sock, lock,))
        recieving = threading.Thread(target=recv_packet, args=(node.sock, recv_neighbors, lock,))

        sending.start()
        recieving.start()

    else:
        print("Incorrect number of arguments")
        print("""usage:cnnode <local-port> receive <neighbor1-port> <loss-rate-1> ... <neighborM-port> 
                <loss-rate-M> send <neighbor(M+1)-port> ... <neighborN-port> [last]""")

if __name__ == '__main__':
    main(sys.argv[1:])

