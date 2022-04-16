import sys
import socket 
import time

SIZE = 4096
PROMPT = ''
MAIN_P = 'routenode.py'

def Die(message, error = True):
    '''
    Prints message and exits.
    :return: None
    '''
    if error:
        print('error: {0}'.format(message))
    else:
        print('{0}'.format(message))
    sys.exit()

def pmessage(message, brackets=True):
    '''
    Displays special prompt w/ message
    :return: None
    '''
    if(brackets):
        print('\n'+ PROMPT + '[' + str(time.time()) + '] ' + str(message) + PROMPT, end ='')
    else:
        print(PROMPT + ' ' + message, end = ' ')
        sys.stdout.flush()

def Port(p, die = True):
    '''
    Checks to see if port number is valid.
    :return: None
    '''
    try: 
        port = int(p)
        if(port < 1024 or port > 65535):
            raise ValueError
    except ValueError as ve:
        if die:
                Die('invalid port number {0}'.format(p))
        else:
                raise ValueError           
    return port


def Socket(port):
    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    try:
        sock.bind(('0.0.0.0', port))
    except Exception as e:
        Die('cannot bind to port {0}'.format(port))
    return sock

def Cost(c, die = True):
    try:
        cost = int(c)
        if cost < 0:
            raise ValueError
    except ValueError as ve:
        if die:
                Die('invalid edge cost {0}'.format(c))
        else:
                raise ValueError
        return cost

def Send(socket, message, dest_addr):
    '''
    Sends message through socket to dest_addr
    :return: None
    '''
    try:
        socket.sendto(message, dest_addr)
    except Exception as e:
        Die(str(e) + ' unable to send message to ({0}, {1})'.format(dest_addr[0], dest_addr[1]))
