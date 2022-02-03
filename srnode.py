#! /usr/bin/python3

import sys
import socket
import time
import threading
import random

# Packet class contains its data, sequence number, and expiration time
class packet:
    def __init__(self, data, sequence, expiration):
        self.data = data
        self.sequence = int(sequence)
        self.expiration = float(expiration)

    def __str__(self):
        return str(self.sequence) + "|" + self.data

# Gives the oldest timeout in the array
def find_min(window):
        soonest_expiration = window[0]

        for packet in window:
            if packet.expiration < soonest_expiration.expiration:
                soonest_expiration = packet
        return soonest_expiration

# Function determines if a packet should be dropped
def not_lost(deterministic, packet_number, p):
    chance = random.randint(0,100)
    if deterministic and (packet_number % p) == 0:
        return False
    elif not deterministic and  p*100 > chance:
        return False
    else:
        return True

# Prints the recieved message
def print_buffer(recieved):
    message = ""
    buffer_length = len(recieved)

    for char in range(buffer_length):
        message +=  recieved[char]
    return message

# Removes a packet from the buffer after it has been acked
def remove_ack_packet(send_buffer, sequence):
    for pack in send_buffer:
        if pack.sequence == sequence:
            send_buffer.remove(pack)
            return

# Determines the current starting sequence for the receive window 
def window_start_recieve(window):
    for i in range(len(window)):
        if i != window[i]:
            return i
    return len(window)

# Determines if a packet was dropped based off the sequence just recieved
def packet_dropped(window, new_sequence):
    if len(window) == 0:
        sequence = -1
    else:
        sequence = window[-1]
    return sequence + 1 != new_sequence

# If a packet was recieved out of order
def packet_out_order(window, new_sequence):
    return new_sequence != window_start_recieve(window)

#Formats the recieved message for printing
def build_message(message):
    string = ""
    for word in message:
        string += word + " "
    return string.strip()

# Threaded function that handles all messages recieved on the specified port and sends ACKs
def recieve_message(sender_window, lock, self_socket, peer, deterministic, p):

    buf = 4096

    while True:
        self_socket.settimeout(None)
        recieve_buffer = {}
        recieving = True
        recieve_window = []
        packet_count = 0
        dropped_packets = 0 
        expected_ack = 0

        while recieving:
            data, addr = self_socket.recvfrom(buf)
            message = data.decode("utf-8").split("|")

            # Handle ACK message
            if message[0] == "*ACK*":
                if expected_ack < int(message[2]):
                    expected_ack = int(message[2])
                expected_ack = sender_window[0].sequence
                lock.acquire()
                remove_ack_packet(sender_window, int(message[1]))
                lock.release()
                if int(message[1]) > expected_ack:
                    print("[{}] ACK{} dropped".format(time.time(), expected_ack))
                print("[{}] ACK{} recieved, window starts at {}".format(time.time(), message[1], expected_ack))
                expected_ack += 1
            elif message != "":
                message_length = int(message[2])

                # If the sequence number is already been recieved its a duplicate
                if int(message[0]) in recieve_buffer:
                    print("[{}] duplicate packet{} {} recieved, discarded".format(time.time(), message[0], message[1]))
                    msg = "*ACK*|" + message[0] + "|" + str(window_start_recieve(recieve_window))
                    self_socket.sendto(msg.encode("utf-8"), peer)
                    packet_count += 1
                
                # Not a duplicate packet, send an ACK
                else:
                    lock.acquire()
                    msg = "*ACK*|" + message[0] + "|" + str(window_start_recieve(recieve_window))
                    lock.release()
                    if not_lost(deterministic, packet_count, p):
                        self_socket.sendto(msg.encode("utf-8"), peer)

                    # Packet could be out of order, or if recieving wrong sequence number could be dropped
                    packet_count += 1
                    out_of_order = packet_out_order(recieve_window, int(message[0]))
                    if not out_of_order:
                        pack_drop = False
                    else:
                        pack_drop = packet_dropped(recieve_window, int(message[0]))
                    recieve_window.append(int(message[0]))
                    recieve_window.sort()
                    
                    # Alert user of recieved packet status
                    if pack_drop:
                        print("[{}] packet{} dropped".format(time.time(), int(message[0]) -1))
                        dropped_packets += 1
                    if out_of_order:
                        print("[{}] packet{} {} recieved out of order, buffered".format(time.time(), message[0], message[1]))
                    else:
                        print("[{}] packet{} {} recieved".format(time.time(), message[0], message[1]))
                    print("[{}] ACK{} sent, window starts at {}".format(time.time(), 
                       message[0], window_start_recieve(recieve_window)))

                    recieve_buffer[int(message[0])] = message[1]

                #Once the client has recieved the full message stop and print it
                if len(recieve_buffer)  == message_length:
                    recieving = False
        print("[{}] message recieved: {}".format(time.time(), print_buffer(recieve_buffer)))
        print("[Summary] {}/{} packets dropped, loss rate = {}%".format(dropped_packets, packet_count, 
            dropped_packets/packet_count))

# Thread function for sending messages, not ACKs
def send_message(sender_window, lock, socket, peer, window_size, deterministic, p):

    while True:
        message = input("node> ").split()

        # Make sure user input matches expected format
        if len(message) > 1 and message[0] == "send":
            message.pop(0)
            data_list = build_message(message)
            message_length = len(data_list)
            seq = 0
            packet_count = 1
            sending = True

            # Only send while there are still chars to send or messages to be ACK'd
            while sending:
 
                # If there is room in the window, add another packet and attempt to send it
                window_level = len(sender_window)

                # Checks there is enough room in the window or reached the end of the message
                if seq < message_length and window_level < window_size :

                    # Create a new packet and add it to the window
                    new_packet = packet(data_list[seq], seq, 0)
                    sender_window.append(new_packet)
                    seq += 1
                    msg = str(new_packet) + "|" + str(message_length)
                    
                    # Send the packet and start its timer
                    new_packet.expiration = time.time() + 0.5
                    print("[{}] packet{} {} sent".format(time.time(),new_packet.sequence, new_packet.data))
                    if not_lost(deterministic, packet_count, p):
                        socket.sendto(msg.encode("utf-8"), peer)
                    packet_count += 1

                # Once the window is empty, all packets have been sent
                if len(sender_window) == 0:
                    sending = False

                if sending:
                    # Check if a packet has timed out
                    lock.acquire()
                    oldest_packet = find_min(sender_window)
                    lock.release()

                    # If a packet has timed out resend it
                    if oldest_packet.expiration < time.time():
                        print("[{}] packet{} timeout, resending".format(time.time(), oldest_packet.sequence))
                        msg = str(oldest_packet) + "|" + str(message_length)
                        lock.acquire()
                        oldest_packet.expiration = time.time() + 0.5
                        lock.release()
                        socket.sendto(msg.encode("utf-8"), peer)
                        packet_count += 1

def main():
    args = len(sys.argv)
    
    if args == 6:
        self_port = int(sys.argv[1])
        peer_port = int(sys.argv[2])
        window_size = int(sys.argv[3])
        function = sys.argv[4]

        if (self_port > 65535 or self_port < 1024) or (peer_port > 65535 or peer_port < 1024):
            print("Port number out of range")
            sys.exit()
    
        # Probabilistic packet dropping
        p = float(sys.argv[5])
    
        if function == "-p":
            if 0 <= p  <= 1:
                deterministic = False
            else:
                print("Probability range: [0,1]")
                sys.exit()

        # Deterministic packet dropping
        elif function == "-d":

            if p > 0:
                deterministic = True
            else:
                print("Deterministic drops must be greater than 0")
                sys.exit()   
        else:
            print("Incorrect function option use -p or -d")
            sys.exit()

        self_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self_sock.bind(('127.0.0.1', self_port))
        peer = ("127.0.0.1", peer_port)

        lock = threading.Lock()
        sender_window = []

        sending = threading.Thread(target=send_message, args=(sender_window, lock, self_sock, peer,
            window_size, deterministic, p,))
        recieving = threading.Thread(target=recieve_message, args=(sender_window, lock, self_sock, peer,
            deterministic, p,))
        sending.start()
        recieving.start()
    
    else:
        print("Incorrect number of arguments")
        print("usage: srnode <self-port> <peer-port> <window-size> [ -d <value-of-n> | -p <value-of-p>]")

if __name__ == '__main__':
    main()

