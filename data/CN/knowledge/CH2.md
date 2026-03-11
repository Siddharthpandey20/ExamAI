# CH2

---

## Document Overview

**Subject:** Computer Networks

**Summary:** The Application Layer is the highest layer of the OSI model, responsible for providing services and protocols for applications to communicate with each other. It provides services such as email, file transfer, and video streaming, and is implemented using various protocols and technologies, including TCP/IP, HTTP, FTP, SMTP, and DNS. The chapter also discusses the use of HTTP cookies for state maintenance and the importance of maintaining user privacy. Additionally, it covers TCP socket programming, including creating and connecting to sockets, sending and receiving data, and handling timeouts.

**Core Topics:** Application Layer, OSI model, TCP/IP, HTTP, FTP, SMTP, DNS, P2P, Socket Programming, Presentation Layer, Session Layer, TCP protocol, state maintenance, cookies and privacy, third-party cookies, tracking cookies

**Chapters:**
  - **HTTP Basics** (slides 1-35): HTTP, cookies, state
  - **Application Layer Overview** (slides 36-70): DNS, SMTP, IMAP, HTTP, QUIC, E-mail
  - **DNS and Socket Programming** (slides 71-105): DNS, Domain Name System, DNS Records, DNS Security, Streaming Stored Video, DASH, Content Distribution Networks, CDNs, Socket Programming, UDP, TCP
  - **TCP Socket Programming and Protocols** (slides 106-119): TCP, Socket Programming, Client-Server, Protocols, Timeouts, Exceptions, CDNs, Netflix


---

## Page 1

> **Title:** HTTP Basics (slides 1-35) | **Type:** other | **Concepts:** Application Layer, Computer Networking | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This is the title slide for Chapter 2, "Application Layer," from "Computer Networking: A Top-Down Approach." It also includes disclaimers regarding the use of the PowerPoint slides by the authors.

Chapter 2
Application Layer

A note on the use of these PowerPoint slides:
We’re making these slides freely available to all (faculty, students, readers). They’re in PowerPoint form so you see the animations; and can add, modify, and delete slides (including this one) and slide content to suit your needs. They obviously represent a lot of work on our part. In return for use, we only ask the following:

• If you use these slides (e.g., in a class) that you mention their source (after all, we’d like people to use our book!)
• If you post any slides on a www site, that you note that they are adapted from (or perhaps identical to) our slides, and note our copyright of this material.

For a revision history, see the slide note for this page.

Thanks and enjoy! JFK/KWR

All material copyright 1996-2025
J.F Kurose and K.W. Ross, All Rights Reserved

Computer Networking: A Top-Down Approach 9th edition Jim Kurose, Keith Ross Pearson, 2025

Application Layer: 2-1
---

### Extracted from Image (OCR)

COMPUTER
NETWORKING
9/E
A TOP-DOWN APPROACH
KUROSEROSS

---

## Page 2

> **Title:** Application Layer Overview (slides 36-70) | **Type:** concept | **Concepts:** Application layer, Network applications, Web and HTTP, E-mail, SMTP, IMAP, DNS, Video streaming, Content distribution networks, Socket programming, UDP, TCP | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide provides an overview of the key topics to be covered in the application layer, including principles of network applications, Web and HTTP, email protocols (SMTP, IMAP), DNS, video streaming, CDNs, and socket programming with UDP and TCP.

Application layer: overview

Principles of network

applications
Web and HTTP
E-mail, SMTP, IMAP
The Domain Name System

DNS

video streaming and content

distribution networks
socket programming with

UDP and TCP

Application Layer: 2-2

### Extracted from Image (OCR)

9/E
A TOP-DOWN APPROACH

---

## Page 3

> **Title:** Application Layer Overview (slides 36-70) | **Type:** concept | **Concepts:** Application-layer protocols, Transport-layer service models, Client-server paradigm, Peer-to-peer paradigm, HTTP, SMTP, IMAP, DNS, Video streaming systems, CDNs, Socket API | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide outlines the goals for the application layer, focusing on conceptual and implementation aspects of protocols, transport-layer service models, client-server and peer-to-peer paradigms. It also lists popular protocols like HTTP, SMTP, IMAP, DNS, and CDNs, along with socket API for programming.

Application layer: overview

Our goals:
• conceptual and implementation aspects of application-layer protocols
• transport-layer service models
• client-server paradigm
• peer-to-peer paradigm

• learn about protocols by examining popular application-layer protocols and infrastructure
• HTTP
• SMTP, IMAP
• DNS
• video streaming systems, CDNs

• programming network applications
• socket API

Application Layer: 2-3

---

## Page 4

> **Title:** Application Layer Overview (slides 36-70) | **Type:** concept | **Concepts:** Social media, Web, Text messaging, E-mail, Multi-user network games, Streaming stored video, P2P file sharing, Voice over IP, Real-time video conferencing, Internet search, Remote login | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide lists a variety of common network applications, including social media, web, email, multi-user games, streaming video, P2P file sharing, VoIP, video conferencing, Internet search, and remote login.

Some network apps

social media
Web
text messaging
e-mail
multi-user network games
streaming stored video

(YouTube, Hulu, Netflix) 
P2P file sharing

voice over IP 
real-time video conferencing

(e.g., Zoom)
Internet search
remote login
…

Q: your favorites?

Application Layer: 2-4

---

## Page 5

> **Title:** Application Layer Overview (slides 36-70) | **Type:** diagram_explanation | **Concepts:** Network app creation, End systems, Network-core devices, Application development, Network layers | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide explains how to create network applications by writing programs that run on different end systems and communicate over the network. It emphasizes that network-core devices do not run user applications, allowing for rapid application development on end systems.

mobile network
home network
enterprise
network
national or global ISP
local or regional ISP
datacenter network
content provider network
application
transport
network
data link
physical

Creating a network app
write programs that:
• run on (different) end systems
• communicate over network
• e.g., web server software
communicates with browser software
no need to write software for network-core devices
• network-core devices do not run user applications
• applications on end systems allows for rapid app development, propagation

Application Layer: 2-5
---

### Table 1

| Creating a network app |  |
| --- | --- |
|  | application |
|  | transport |
|  |  |
| write programs that: | network
mobile network |
|  | data link |
|  | physical |
|  run on (different) end systems |  |

### Table 2

|  |  | local or |  |  |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |
| no need to write software for |  | regional ISP |  |  |
| network-core devices |  |  |  |  |
|  | home network |  |  |  |
|  |  |  | content |  |
|  | application |  |  |  |
|  |  |  | provider |  |
|  |  |  |  |  |
|  network-core devices do not run user | transport |  |  |  |
|  |  |  | network | datacenter |
|  | network |  |  |  |
|  |  |  | application |  |
| applications | data link |  |  | network |
|  |  |  |  |  |
|  |  |  | transport |  |
|  | physical |  |  |  |
|  |  |  | network |  |
|  |  |  | data link |  |
|  |  |  |  |  |
|  applications on end systems  allows |  |  | physical |  |

---

## Page 6

> **Title:** Application Layer Overview (slides 36-70) | **Type:** definition | **Concepts:** Client-server paradigm, Server, Always-on host, Permanent IP address, Data centers, Clients, Intermittently connected, Dynamic IP addresses, HTTP, IMAP, FTP | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide defines the client-server paradigm, where servers are always-on hosts with permanent IP addresses, often located in data centers. Clients contact and communicate with servers, may be intermittently connected, and typically have dynamic IP addresses; examples include HTTP, IMAP, and FTP.

mobile network
home network
enterprise network
network
national or global ISP
local or regional ISP
datacenter network
content provider network

Client-server paradigm

server:
• always-on host
• permanent IP address
• often in data centers, for scaling

clients:
• contact, communicate with server
• may be intermittently connected
• may have dynamic IP addresses
• do not communicate directly with each other
• examples: HTTP, IMAP, FTP

Application Layer: 2-6
---

### Table 1

| Client-server paradigm |  |  |  |  |
| --- | --- | --- | --- | --- |
| server: |  |  |  |  |
|  | mobile network |  |  |  |
|  |  |  |  |  |
|  always-on host |  |  | national or global ISP |  |
|  permanent IP address |  |  |  |  |
|  often in data centers, for scaling |  |  |  |  |
| clients: |  | local or |  |  |
|  |  | regional ISP |  |  |
|  contact, communicate with server |  |  |  |  |
|  | home network |  |  |  |
|  |  |  |  |  |
|  may be intermittently connected |  |  | content |  |
|  |  |  | provider |  |
|  |  |  |  |  |
|  may have dynamic IP addresses |  |  | network | datacenter 
network |
|  do not communicate directly with |  |  |  |  |
| each other |  |  |  |  |
|  | enterprise |  |  |  |
|  |  |  |  |  |
|  examples: HTTP, IMAP, FTP | network |  |  |  |
|  |  |  |  | Application Layer: 2-6 |

---

## Page 7

> **Title:** Application Layer Overview (slides 36-70) | **Type:** definition | **Concepts:** Peer-to-peer architecture, No always-on server, Arbitrary end systems, Self scalability, Intermittently connected peers, Dynamic IP addresses, Complex management, P2P file sharing, BitTorrent | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide describes the peer-to-peer architecture, characterized by no always-on server and direct communication between arbitrary end systems. Peers request and provide services, leading to self-scalability, but also complex management due to intermittent connections and changing IP addresses, exemplified by BitTorrent.

mobile network
home network
enterprise
network
national or global ISP
local or
regional ISP
datacenter
network
content
provider
network
Peer-peer architecture
• no always-on server
• arbitrary end systems directly
communicate
• peers request service from other
peers, provide service in return to
other peers
• self scalability – new peers bring new
service capacity, as well as new service
demands
• peers are intermittently connected
and change IP addresses
• complex management
• example: P2P file sharing [BitTorrent]
Application Layer: 2-7
---

### Table 1

| Peer-peer architecture |  |  |  |  |
| --- | --- | --- | --- | --- |
|  no always-on server |  |  |  |  |
|  | mobile network |  |  |  |
|  |  |  |  |  |
|  arbitrary end systems directly |  |  | national or global ISP |  |
| communicate |  |  |  |  |
|  peers request service from other |  |  |  |  |
| peers, provide service in return to |  |  |  |  |
| other peers |  | local or |  |  |
|  |  | regional ISP |  |  |
| •
self scalability – new peers bring new |  |  |  |  |
| service capacity, as well as new service | home network |  |  |  |
|  |  |  | content |  |
|  |  |  |  |  |
| demands |  |  | provider |  |
|  |  |  | network | datacenter |
|  |  |  |  |  |
|  peers are intermittently connected |  |  |  | network |
| and change IP addresses |  |  |  |  |
| • complex management |  |  |  |  |
|  | enterprise |  |  |  |
|  | network |  |  |  |
|  example: P2P file sharing [BitTorrent] |  |  |  |  |
|  |  |  |  | Application Layer: 2-7 |

---

## Page 8

> **Title:** DNS and Socket Programming (slides 71-105) | **Type:** definition | **Concepts:** Process, Inter-process communication, Messages, P2P architectures, Client process, Server process | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide defines a process as a program running within a host, distinguishing between inter-process communication within the same host and message exchange between processes on different hosts. It also defines client processes as those initiating communication and server processes as those waiting to be contacted.

Processes communicating

process: program running

within a host
within same host, two

processes communicate 
using  inter-process 
communication (defined by 
OS)
processes in different hosts

communicate by exchanging 
messages

note: applications with

P2P architectures have 
client processes & 
server processes

client process: process that

initiates communication
server process: process

that waits to be contacted

clients, servers

Application Layer: 2-8

---

## Page 9

> **Title:** DNS and Socket Programming (slides 71-105) | **Type:** diagram_explanation | **Concepts:** Sockets, Messages, Transport infrastructure, Receiving process, Sending process, OS control, App developer control, Network layers | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide explains sockets as the interface through which processes send and receive messages, analogous to a door. It illustrates how a sending process relies on the transport infrastructure to deliver a message to a socket at the receiving process, involving two sockets on each side.

Sockets

process sends/receives messages to/from its socket
socket analogous to door

• sending process shoves message out door
• sending process relies on transport infrastructure on other side of 
door to deliver message to socket at receiving process
• two sockets involved: one on each side

Internet

controlled
by OS

controlled by
app developer

transport

application

physical

link

network

process

transport

application

physical

link

network

process
socket

Application Layer: 2-9

### Table 1

| application
process
transport |  |
| --- | --- |
|  |  |
| network
link
physical |  |
|  |  |
|  |  |

### Table 2

| application
process
transport |  |
| --- | --- |
|  |  |
| network
link
physical |  |
|  |  |
|  |  |

### Table 3

| application
process
transport |
| --- |
| network |
| link |
| physical |

### Table 4

| application
process
transport |
| --- |
| network |
| link |
| physical |

---

## Page 10

> **Title:** DNS and Socket Programming (slides 71-105) | **Type:** concept | **Concepts:** Process identifier, IP address, Port numbers, HTTP server port 80, Mail server port 25, gaia.cs.umass.edu, 128.119.245.12 | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide explains that processes require both a unique IP address of the host and a specific port number to be identified and receive messages. It provides examples of standard port numbers like 80 for HTTP servers and 25 for mail servers.

Addressing processes

to receive messages, process

must have identifier
host device has unique 32-bit

IP address
Q: does  IP address of host on

which process runs suffice for 
identifying the process?

identifier includes both IP address

and port numbers associated with 
process on host.
example port numbers:

• HTTP server: 80
• mail server: 25
to send HTTP message to

gaia.cs.umass.edu web server:

• IP address: 128.119.245.12
• port number: 80
more shortly…

A: no, many processes

can be running on 
same host

Application Layer: 2-10

---

## Page 11

> **Title:** Application Layer Overview (slides 36-70) | **Type:** definition | **Concepts:** Application-layer protocol, Message types, Message syntax, Message semantics, Rules, Open protocols, RFCs, Interoperability, HTTP, SMTP, Proprietary protocols, Zoom | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide defines an application-layer protocol by its message types, syntax, semantics, and rules for message exchange. It differentiates between open protocols, defined in RFCs for interoperability like HTTP and SMTP, and proprietary protocols like Zoom.

An application-layer protocol defines:

types of messages exchanged,

• e.g., request, response 
message syntax:

• what fields in messages & 
how fields are delineated
message semantics

• meaning of information in 
fields
rules for when and how

processes send & respond to 
messages

open protocols:

defined in RFCs, everyone

has access to protocol 
definition
allows for interoperability
e.g., HTTP, SMTP
proprietary protocols:

e.g., Zoom

Application Layer: 2-11

---

## Page 12

> **Title:** Application Layer Overview (slides 36-70) | **Type:** concept | **Concepts:** Transport service requirements, Data integrity, Reliable data transfer, Loss tolerance, Timing, Low delay, Throughput, Minimum throughput, Elastic apps, Security, Encryption | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide outlines the key transport service requirements for applications, including data integrity (reliable or loss-tolerant), timing (low delay), throughput (minimum or elastic), and security (encryption, data integrity).

What transport service does an app need?

data integrity
some apps (e.g., file transfer,

web transactions) require 
100% reliable data transfer
other apps (e.g., audio) can

tolerate some loss

timing
some apps (e.g., Internet

telephony, interactive games) 
require low delay to be “effective”

throughput
some apps (e.g., multimedia)

require minimum amount of 
throughput to be “effective”
other apps (“elastic apps”)

make use of whatever 
throughput they get

security
encryption, data integrity,

…

Application Layer: 2-12

---

## Page 13

> **Title:** Application Layer Overview (slides 36-70) | **Type:** table | **Concepts:** Transport service requirements, File transfer, E-mail, Web documents, Real-time audio/video, Streaming audio/video, Interactive games, Text messaging, Data loss, Throughput, Time sensitive | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide presents a table summarizing the transport service requirements for various common applications, detailing their needs for data loss tolerance, throughput, and time sensitivity. It shows that some apps require no loss and are elastic (e.g., file transfer, web), while others are loss-tolerant and time-sensitive (e.g., real-time audio/video).

Transport service requirements: common apps

* application
* file transfer/download
* e-mail
* Web documents
* real-time audio/video
* streaming audio/video
* interactive games
* text messaging
* data loss
	+ no loss
	+ no loss
	+ no loss
	+ loss-tolerant
* throughput
	+ elastic
	+ elastic
	+ elastic
	+ audio: 5Kbps-1Mbps
	+ video: 10Kbps-5Mbps
	+ same as above
	+ Kbps+
	+ elastic
* time sensitive?
	+ no
	+ no
	+ no
	+ yes, 10’s msec
	+ yes, few secs
	+ yes, 10’s msec
	+ yes and no
Application Layer: 2-13
---

---

## Page 14

> **Title:** Application Layer Overview (slides 36-70) | **Type:** comparison | **Concepts:** TCP service, Reliable transport, Flow control, Congestion control, Connection-oriented, UDP service, Unreliable data transfer, Timing, Minimum throughput guarantee, Security | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide compares TCP and UDP transport protocols, highlighting TCP's reliable, flow-controlled, congestion-controlled, and connection-oriented services without timing or throughput guarantees. In contrast, UDP offers unreliable data transfer without any of these guarantees, prompting a question about its utility.

Internet transport protocols services

TCP service:
• reliable transport between sending and receiving process
• flow control: sender won’t overwhelm receiver
• congestion control: throttle sender when network overloaded
• connection-oriented: setup required between client and server processes
• does not provide: timing, minimum throughput guarantee, security

UDP service:
• unreliable data transfer between sending and receiving process
• does not provide: reliability, flow control, congestion control, timing, throughput guarantee, security, or connection setup.

Q: why bother? Why is there a UDP?

Application Layer: 2-14

---

## Page 15

> **Title:** Application Layer Overview (slides 36-70) | **Type:** table | **Concepts:** Internet applications, Transport protocols, FTP, SMTP, HTTP, SIP, RTP, DASH, WOW, FPS, TCP, UDP, File transfer, E-mail, Web documents, Internet telephony, Streaming audio/video, Interactive games | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide presents a table mapping various Internet applications to their respective application-layer and transport protocols. It shows that common applications like file transfer, email, and web documents primarily use TCP, while telephony, streaming, and games might use either TCP or UDP.

Internet applications, and transport protocols

application

* file transfer/download
* e-mail
* Web documents
* Internet telephony
* streaming audio/video
* interactive games

application
layer protocol

* FTP [RFC 959]
* SMTP [RFC 5321]
* HTTP [RFC 7230, 9110]
* SIP [RFC 3261], RTP [RFC 3550], or proprietary 
* HTTP [RFC 7230], DASH
* WOW, FPS (proprietary)

transport protocol

* TCP
* TCP
* TCP
* TCP or UDP
* TCP
* UDP or TCP

Application Layer: 2-15

---

## Page 16

> **Title:** Application Layer Overview (slides 36-70) | **Type:** concept | **Concepts:** Securing TCP, Vanilla TCP & UDP sockets, No encryption, Cleartext passwords, Transport Layer Security (TLS), Encrypted TCP connections, Data integrity, End-point authentication, TLS libraries | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide discusses securing TCP connections, noting that vanilla TCP and UDP sockets lack encryption, sending cleartext passwords. It introduces Transport Layer Security (TLS) as a solution, providing encrypted TCP connections, data integrity, and end-point authentication, implemented via application-layer libraries.

Securing TCP

Vanilla TCP & UDP sockets:

• no encryption
• cleartext passwords sent into socket

traverse Internet in cleartext (!)
Transport Layer Security (TLS)

• provides encrypted TCP connections
• data integrity
• end-point authentication

TLS implemented in
application layer

• apps use TLS libraries, that

use TCP in turn
• cleartext sent into “socket”

traverse Internet encrypted
• more: Chapter 8

Application Layer: 2-16
---

---

## Page 17

> **Title:** Application Layer Overview (slides 36-70) | **Type:** concept | **Concepts:** Application layer, Network applications, Web and HTTP, E-mail, SMTP, IMAP, DNS, Video streaming, Content distribution networks, Socket programming, UDP, TCP | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide provides a summary overview of the topics covered in the application layer, including principles of network applications, Web and HTTP, email protocols (SMTP, IMAP), DNS, video streaming, CDNs, and socket programming with UDP and TCP.

Application layer: overview

• Principles of network applications
• Web and HTTP
• E-mail, SMTP, IMAP
• The Domain Name System
• DNS
• video streaming and content distribution networks
• socket programming with UDP and TCP
• Application Layer: 2-17

### Extracted from Image (OCR)

9/E
A TOP-DOWN APPROACH

---

## Page 18

> **Title:** HTTP Basics (slides 1-35) | **Type:** concept | **Concepts:** Web page, Objects, Web servers, HTML file, JPEG image, Java applet, Audio file, Base HTML-file, Referenced objects, URL, Host name, Path name | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide provides a quick review of web pages, explaining they consist of multiple objects (e.g., HTML, images) that can be stored on different servers. Each object is addressable by a URL, which includes a host name and a path name.

Web and HTTP

First, a quick review…
• web page consists of objects, each of which can be stored on different Web servers
• object can be HTML file, JPEG image, Java applet, audio file,…
• web page consists of base HTML-file which includes several referenced objects, each addressable by a URL, e.g., www.someschool.edu/someDept/pic.gif
• host name
• path name

Application Layer: 2-18
---

---

## Page 19

> **Title:** HTTP Basics (slides 1-35) | **Type:** definition | **Concepts:** HTTP, Hypertext transfer protocol, Web’s application-layer protocol, Client/server model, Client, Browser, Server, Web server, Apache Web server | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide defines HTTP as the web's application-layer protocol, operating on a client/server model. The client (browser) requests and displays web objects, while the server (web server) sends objects in response to these requests.

HTTP overview

HTTP: hypertext transfer protocol
• Web’s application-layer protocol
• client/server model:
  • client: browser that requests, receives, (using HTTP protocol) and “displays” Web objects 
  • server: Web server sends (using HTTP protocol) objects in response to requests

iPhone running

Safari browser

PC running
Firefox browser

server running

Apache Web server

Application Layer: 2-19

### Table 1

| HTTP overview |  |  |
| --- | --- | --- |
| HTTP: hypertext transfer protocol |  |  |
|  Web’s application-layer protocol |  |  |
|  client/server model: |  |  |
|  | PC running |  |
|  | Firefox browser |  |
| • client: browser that requests, |  |  |
| receives, (using HTTP protocol) and |  |  |
| “displays” Web objects |  |  |
|  |  | server running |
| • server: Web server sends (using |  |  |
|  |  | Apache Web |
| HTTP protocol) objects in response |  | server |
| to requests |  |  |
|  | iPhone running |  |
|  | Safari browser |  |
|  |  | Application Layer: 2-19 |

---

## Page 20

> **Title:** HTTP Basics (slides 1-35) | **Type:** concept | **Concepts:** HTTP uses TCP, TCP connection, Port 80, HTTP messages, Browser, Web server, HTTP is stateless, Past client requests, Stateful protocols complexity, Server/client crashes | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide explains that HTTP uses TCP, where a client initiates a TCP connection to the server on port 80 to exchange messages, then closes the connection. It also highlights that HTTP is "stateless," meaning the server maintains no information about past client requests, simplifying design but making stateful protocols more complex to manage.

HTTP overview (continued)

HTTP uses TCP:
• client initiates TCP connection
(creates socket) to server, port 80
• server accepts TCP connection
from client
• HTTP messages (application-layer
protocol messages) exchanged
between browser (HTTP client) and
Web server (HTTP server)
• TCP connection closed

HTTP is “stateless”
• server maintains no
information about past client
requests

protocols that maintain
“state” are complex!
• past history (state) must be
maintained
• if server/client crashes, their
views of “state” may be
inconsistent, must be reconciled

Application Layer: 2-20

---

## Page 21

> **Title:** HTTP Basics (slides 1-35) | **Type:** comparison | **Concepts:** HTTP connections, Non-persistent HTTP, TCP connection, One object per connection, Multiple connections, Persistent HTTP, Multiple objects per connection, Single TCP connection | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide compares two types of HTTP connections: non-persistent HTTP, where a new TCP connection is opened for each object and then closed, and persistent HTTP, where a single TCP connection remains open to send multiple objects between the client and server.

HTTP connections: two types

Non-persistent HTTP
1. TCP connection opened
2. at most one object sent
over TCP connection
3. TCP connection closed

downloading multiple objects required multiple connections

Persistent HTTP
• TCP connection opened to a server
• multiple objects can be sent over single TCP connection between client, and that server
• TCP connection closed

Application Layer: 2-21

---

## Page 22

> **Title:** HTTP Basics (slides 1-35) | **Type:** example | **Concepts:** Non-persistent HTTP, URL, HTTP client, TCP connection, HTTP server, Port 80, HTTP request message, HTTP response message | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide illustrates the initial steps of non-persistent HTTP, where a client first initiates a TCP connection to a server on port 80, then sends an HTTP request message for an object. The server accepts the connection, receives the request, forms a response, and sends it back.

Non-persistent HTTP: example

User enters URL:

1a. HTTP client initiates TCP connection to HTTP server (process) at www.someSchool.edu on port 80

2. HTTP client sends HTTP request message (containing URL) into TCP connection socket. Message indicates that client wants object someDepartment/home.index

1b. HTTP server at host www.someSchool.edu waiting for TCP connection at port 80 “accepts” connection, notifying client

3. HTTP server receives request message, forms response message containing requested object, and sends message into its socket

Application Layer: 2-22
---

### Table 1

|  | (process) at www.someSchool.edu on | www.someSchool.edu waiting for TCP |
| --- | --- | --- |
|  | port 80 |  |
|  |  | connection at port 80  “accepts” |
|  |  | connection, notifying client |
|  | 2. HTTP client sends HTTP |  |
|  | request message (containing |  |
|  |  | 3. HTTP server receives request message, |
|  | URL) into TCP connection |  |
|  |  | forms response message containing |
|  | socket. Message indicates |  |
|  |  | requested object, and sends message |
|  |  |  |
| time | that client wants object |  |
|  | someDepartment/home.index | into its socket |

---

## Page 23

> **Title:** HTTP Basics (slides 1-35) | **Type:** example | **Concepts:** Non-persistent HTTP, HTTP server, TCP connection close, HTTP client, Response message, HTML file, Referenced jpeg objects, Repeated steps | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide continues the non-persistent HTTP example, showing that after the server sends the initial HTML file, it closes the TCP connection. The client then parses the HTML, identifies referenced JPEG objects, and repeats the entire connection and request process for each additional object.

Non-persistent HTTP: example (cont.)

User enters URL:

www.someSchool.edu/someDepartment/home.index

5. HTTP client receives response

message containing html file, displays html. Parsing html file, finds 10 referenced jpeg objects

6. Steps 1-5 repeated for each of 10 jpeg objects

4. HTTP server closes TCP connection. time

Application Layer: 2-23
---

### Table 1

| Non-persistent HTTP: example (cont.) |  |
| --- | --- |
|  |  |
| www.someSchool.edu/someDepartment/home.index
User enters URL: |  |
| (containing text, references to 10 jpeg images) |  |
| 4. HTTP server closes TCP |  |
| connection. |  |
| 5. HTTP client receives response |  |
| message containing html file, |  |
| displays html.  Parsing html file, |  |
| finds 10 referenced jpeg  objects |  |
| 6. Steps 1-5 repeated for |  |
| each of 10 jpeg objects |  |
| time |  |
|  | Application Layer: 2-23 |

---

## Page 24

> **Title:** HTTP Basics (slides 1-35) | **Type:** numerical_example | **Concepts:** Non-persistent HTTP response time, RTT (Round-trip time), TCP connection initiation, HTTP request, HTTP response, File transmission time | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide defines RTT as the time for a small packet to travel from client to server and back, then calculates the non-persistent HTTP response time. It shows that for each object, the response time is 2 RTTs (one for TCP setup, one for request/response) plus the file transmission time.

Non-persistent HTTP: response time

RTT (definition): time for a small packet to travel from client to server and back
HTTP response time (per object):
one RTT to initiate TCP connection
one RTT for HTTP request and first few bytes of HTTP response to return
object/file transmission time
time to transmit file
initiate TCP connection
RTT
request file
RTT
file received
time
time

Non-persistent HTTP response time = 2RTT + file transmission time

Application Layer: 2-24
---

### Table 1

| Non-persistent HTTP: response time |  |  |  |  |
| --- | --- | --- | --- | --- |
| RTT (definition): time for a small |  |  |  |  |
| packet to travel from client to |  |  |  |  |
|  | initiate TCP |  |  |  |
| server and back | connection |  |  |  |
|  | RTT |  |  |  |
| HTTP response time (per object): |  |  |  |  |
|  | request file |  |  |  |
|  one RTT to initiate TCP connection |  |  |  |  |
|  |  |  |  | time to |
|  one RTT for HTTP request and first few | RTT |  |  |  |
|  |  |  |  | transmit |
| bytes of HTTP response to return |  |  |  |  |
|  |  |  | file |  |
|  | file received |  |  |  |
|  object/file transmission time |  |  |  |  |
|  |  | time | time |  |
|  | Non-persistent HTTP response time =  2RTT+ file transmission  time |  |  |  |
|  |  |  |  | Application Layer: 2-24 |

---

## Page 25

> **Title:** HTTP Basics (slides 1-35) | **Type:** comparison | **Concepts:** Non-persistent HTTP issues, 2 RTTs per object, OS overhead, Parallel TCP connections, Persistent HTTP (HTTP 1.1), Connection open, Subsequent HTTP messages, Referenced objects, Response time reduction | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide highlights the issues with non-persistent HTTP, such as requiring 2 RTTs per object and OS overhead. It then introduces Persistent HTTP (HTTP 1.1), which keeps the connection open for multiple objects, allowing subsequent messages over the same connection and potentially cutting response time in half.

Persistent HTTP (HTTP 1.1)

Non-persistent HTTP issues:

• requires 2 RTTs per object
• OS overhead for each TCP connection
• browsers often open multiple parallel TCP connections to fetch referenced objects in parallel

Persistent HTTP (HTTP1.1):

• server leaves connection open after sending response
• subsequent HTTP messages between same client/server sent over open connection
• client sends requests as soon as it encounters a referenced object
• as little as one RTT for all the referenced objects (cutting response time in half)

Application Layer: 2-25
---

---

## Page 26

> **Title:** HTTP Basics (slides 1-35) | **Type:** concept | **Concepts:** HTTP request message, ASCII format, header lines, request line, GET, POST, HEAD | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide introduces the HTTP request message, describing its ASCII format and components like header lines and the request line, providing an example of a GET request.

HTTP request message

• two types of HTTP messages: request, response
• HTTP request message:
  • ASCII (human-readable format)

header

lines

GET /index.html HTTP/1.1
Host: www-net.cs.umass.edu
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:80.0) Gecko/20100101 Firefox/80.0 
Accept: text/html,application/xhtml+xml
Accept-Language: en-us,en;q=0.5
Accept-Encoding: gzip,deflate
Connection: keep-alive

carriage return character
line-feed character
request line (GET, POST, HEAD commands)
carriage return, line feed at start of line indicates end of header lines

* Check out the online interactive exercises for more examples: http://gaia.cs.umass.edu/kurose_ross/interactive/
Application Layer: 2-26
---

### Table 1

|  HTTP request message: |
| --- |
| • ASCII (human-readable format) |
| carriage return character |
| line-feed character |
| request line (GET, POST, |
| GET /index.html HTTP/1.1\r\n |
| HEAD commands) |
| Host: www-net.cs.umass.edu\r\n |
| User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X |
| 10.15; rv:80.0) Gecko/20100101 Firefox/80.0 \r\n |
| header |
| Accept: text/html,application/xhtml+xml\r\n |
|  |
| Accept-Language: en-us,en;q=0.5\r\n
lines |
| Accept-Encoding: gzip,deflate\r\n |
| Connection: keep-alive\r\n |
| \r\n |
| carriage return, line feed |

---

## Page 27

> **Title:** HTTP Basics (slides 1-35) | **Type:** diagram_explanation | **Concepts:** HTTP request message format, request line, method, URL, version, header lines, entity body | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide illustrates the general format of an HTTP request message, detailing its structure including the request line (method, URL, version), header lines, and the optional entity body.

HTTP request message: general format

request
line

header
lines

body

method
sp
sp
cr
lf
version
URL

cr
lf
value
header field name

cr
lf
value
header field name

cr
lf

entity body

Application Layer: 2-27

### Table 1

| sp
sp
version
cr
method
URL
lf |  |
| --- | --- |
| value
header field name
cr
lf | ~ |
| ~ |  |

### Table 2

| ~ |  |
| --- | --- |
| value
header field name
cr
lf |  |
| cr
lf |  |
| entity body
~
~ |  |

---

## Page 28

> **Title:** HTTP Basics (slides 1-35) | **Type:** definition | **Concepts:** POST method, GET method (data to server), HEAD method, PUT method | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide describes several HTTP request methods, including POST for sending user input, GET for sending data via URL, HEAD for requesting only headers, and PUT for uploading files.

Other HTTP request messages

POST method:
• web page often includes form
• user input sent from client to
• server in entity body of HTTP POST request message

GET method (for sending data to server):
• include user data in URL field of HTTP
• GET request message (following a ‘?’): www.somesite.com/animalsearch?monkeys&banana

HEAD method:
• requests headers (only) that
• would be returned if specified URL were requested with an HTTP GET method.

PUT method:
• uploads new file (object) to server
• completely replaces file that exists at specified URL with content in entity body of POST HTTP request message

Application Layer: 2-28

### Table 1

| Other HTTP request messages |  |
| --- | --- |
| POST method: | HEAD method: |
|  web page often includes form |  requests headers (only) that |
| input | would be returned if specified |
|  user input sent from client to | URL were requested  with an |
| server in entity body of HTTP | HTTP GET method. |
| POST request message |  |
|  | PUT method: |
|  |  uploads new file (object) to server |
| GET method (for sending data to server): |  |
|  |  completely replaces file that exists |
|  include user data in URL field of HTTP | at specified URL with content in |
| GET request message (following a ‘?’): | entity body of POST HTTP request |
|  | message |
| www.somesite.com/animalsearch?monkeys&banana |  |
|  | Application Layer: 2-28 |

---

## Page 29

> **Title:** HTTP Basics (slides 1-35) | **Type:** concept | **Concepts:** HTTP response message, status line, status code, status phrase, header lines, data | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide introduces the HTTP response message, detailing its structure with a status line, header lines, and the requested data, and provides an example.

HTTP response message

status line (protocol
status code status phrase)

header

lines

data, e.g.,  requested
HTML file

HTTP/1.1 200 OK
Date: Tue, 08 Sep 2020 00:53:20 GMT
Server: Apache/2.4.6 (CentOS)
OpenSSL/1.0.2k-fips PHP/7.4.9 
mod_perl/2.0.11 Perl/v5.16.3
Last-Modified: Tue, 01 Mar 2016 18:57:50 GMT
ETag: "a5b-52d015789ee9e"
Accept-Ranges: bytes
Content-Length: 2651
Content-Type: text/html; charset=UTF-8
\r\n
data data data data data ...

* Check out the online interactive exercises for more examples: http://gaia.cs.umass.edu/kurose_ross/interactive/

Application Layer: 2-29

### Table 1

| HTTP response message |  |  |
| --- | --- | --- |
| status line (protocol |  |  |
|  |  | HTTP/1.1 200 OK |
|  |  |  |
| status code status phrase) |  | Date: Tue, 08 Sep 2020 00:53:20 GMT |
|  |  | Server: Apache/2.4.6 (CentOS) |
|  |  | OpenSSL/1.0.2k-fips PHP/7.4.9 |
|  |  | mod_perl/2.0.11 Perl/v5.16.3 |
|  | header | Last-Modified: Tue, 01 Mar 2016 18:57:50 GMT |
|  |  | ETag: "a5b-52d015789ee9e" |
|  | lines |  |
|  |  | Accept-Ranges: bytes |
|  |  | Content-Length: 2651 |
|  |  | Content-Type: text/html; charset=UTF-8 |
|  |  | \r\n |
| data, e.g.,  requested |  | data data data data data ... |
| HTML file |  |  |
|  | * Check out the online interactive exercises for more examples: http://gaia.cs.umass.edu/kurose_ross/interactive/ |  |
|  |  | Application Layer: 2-29 |

---

## Page 30

> **Title:** HTTP Basics (slides 1-35) | **Type:** definition | **Concepts:** HTTP status codes, 200 OK, 301 Moved Permanently, 400 Bad Request, 404 Not Found, 505 HTTP Version Not Supported | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide lists and explains common HTTP response status codes, such as 200 OK for success, 301 Moved Permanently, 400 Bad Request, 404 Not Found, and 505 HTTP Version Not Supported.

HTTP response status codes

200 OK
• request succeeded, requested object later in this message

301 Moved Permanently
• requested object moved, new location specified later in this message (in Location: field)

400 Bad Request
• request msg not understood by server

404 Not Found
• requested document not found on this server

505 HTTP Version Not Supported
status code appears in 1st line in server-to-client response message.
some sample codes:
Application Layer: 2-30

---

## Page 31

> **Title:** HTTP Basics (slides 1-35) | **Type:** example | **Concepts:** netcat, TCP connection, HTTP GET request, Host header | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide provides an example of how to manually interact with an HTTP server using `netcat` to open a TCP connection and send a minimal GET HTTP request.

Trying out HTTP (client side) for yourself

1. netcat to your favorite Web server:

• opens TCP connection to port 80 (default HTTP server port) at gaia.cs.umass.edu.
• anything typed in will be sent to port 80 at gaia.cs.umass.edu

2. type in a GET HTTP request:

GET /kurose_ross/interactive/index.php HTTP/1.1
Host: gaia.cs.umass.edu
• by typing this in (hit carriage return twice), you send this minimal (but complete) GET request to HTTP server

Application Layer: 2-31

% nc -c -v gaia.cs.umass.edu 80 (for Mac)
>ncat –C gaia.cs.umass.edu 80 (for Windows)
---

---

## Page 32

> **Title:** HTTP Basics (slides 1-35) | **Type:** concept | **Concepts:** HTTP statelessness, multi-step exchanges, stateful protocol, client/server state | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide explains that HTTP interactions are stateless, meaning each request is independent, and contrasts this with stateful protocols that track multi-step exchanges.

Maintaining user/server state: cookies

Recall:  HTTP GET/response

interaction is stateless
• no notion of multi-step exchanges of

HTTP messages to complete a Web 
“transaction”

• no need for client/server to track 
“state” of multi-step exchange
• all HTTP requests are independent of 
each other
• no need for client/server to “recover” 
from a partially-completed-but-never-
completely-completed transaction

a stateful protocol: client makes 
two changes to X, or none at all

time
time

X

X

X’

X’’

X’’

t’

Q: what happens if network connection or 
client crashes at t’ ?

Application Layer: 2-32

### Table 1

| Maintaining user/server state: cookies |  |
| --- | --- |
|  | a stateful protocol: client makes |
| Recall:  HTTP GET/response | two changes to X, or none at all |
| interaction is stateless |  |
|  | X |
|  no notion of multi-step exchanges of |  |
| HTTP messages to complete a Web |  |
|  | X |
| “transaction” |  |
| • no need for client/server to track |  |
|  | X’ |
| “state” of multi-step exchange |  |
|  | t’ |
| • all HTTP requests are independent of |  |
|  | X’’ |
| each other |  |
| • no need for client/server to “recover” |  |
|  | X’’ |
| from a partially-completed-but-never- |  |
|  | time
time |
| completely-completed transaction |  |
|  | Q: what happens if network connection or |
|  | client crashes at t’ ? |
|  | Application Layer: 2-32 |

---

## Page 33

> **Title:** HTTP Basics (slides 1-35) | **Type:** concept | **Concepts:** cookies, user/server state, cookie header line (response), cookie header line (request), cookie file, back-end database, unique ID | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide introduces cookies as a mechanism for Web sites and client browsers to maintain state between transactions, outlining the four key components involved and providing an example of initial site visits.

Maintaining user/server state: cookies

Web sites and client browser use

cookies to maintain some state between transactions
four components:

1) cookie header line of HTTP response message
2) cookie header line in next HTTP request message
3) cookie file kept on user’s host, managed by user’s browser
4) back-end database at Web site

Example:
Susan uses browser on laptop, visits specific e-commerce site for first time
when initial HTTP requests arrives at site, site creates:
• unique ID (aka “cookie”)
• entry in backend database for ID
• subsequent HTTP requests from Susan to this site will contain cookie ID value, allowing site to “identify” Susan

Application Layer: 2-33

---

## Page 34

> **Title:** HTTP Basics (slides 1-35) | **Type:** diagram_explanation | **Concepts:** cookies, client-server interaction, Set-cookie header, cookie file, back-end database | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide illustrates the client-server interaction when using cookies, showing how a server sets a cookie in a response, how the client stores it, and how it's included in subsequent requests to maintain state.

Maintaining user/server state: cookies

client

Amazon server

usual HTTP response msg

usual HTTP response msg

cookie file

one week later:

usual HTTP request msg

cookie: 1678
cookie-
specific

action

access

ebay 8734
usual HTTP request msg
Amazon server

creates ID
1678 for user
create

entry
usual HTTP response

set-cookie: 1678 
ebay 8734
amazon 1678

usual HTTP request msg

cookie: 1678
cookie-
specific

action

access

ebay 8734
amazon 1678

backend
database

time
time
Application Layer: 2-34
---

### Table 1

| Maintaining user/server state: cookies |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
| client |  |  |  |  |  |
|  |  |  | Amazon server |  |  |
| ebay 8734 |  |  |  |  |  |
|  |  | usual HTTP request msg |  |  |  |
|  |  |  | Amazon server |  |  |
| cookie file |  |  | creates ID |  |  |
|  |  | usual HTTP response |  |  |  |
|  |  |  | 1678 for user |  | backend |
|  |  |  |  | create |  |
| ebay 8734 |  | set-cookie: 1678 |  |  |  |
|  |  |  |  | entry |  |
|  |  |  |  |  | database |
| amazon 1678 |  |  |  |  |  |
|  |  | usual HTTP request msg |  |  |  |
|  |  |  | cookie- |  |  |
|  |  |  |  | access |  |
|  |  | cookie: 1678 |  |  |  |
|  |  |  | specific |  |  |
|  |  | usual HTTP response msg |  |  |  |
|  |  |  | action |  |  |
|  | one week later: |  |  |  |  |
|  |  |  |  | access |  |
| ebay 8734 |  | usual HTTP request msg |  |  |  |
| amazon 1678 |  |  | cookie- |  |  |
|  |  | cookie: 1678 |  |  |  |
|  |  |  | specific |  |  |
|  |  | usual HTTP response msg | action |  |  |
|  | time |  | time |  | Application Layer: 2-34 |

---

## Page 35

> **Title:** HTTP Basics (slides 1-35) | **Type:** concept | **Concepts:** cookie uses, authorization, shopping carts, recommendations, user session state, cookies and privacy, third party persistent cookies, tracking cookies, state at protocol endpoints, state in messages | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide discusses the various applications of HTTP cookies, such as authorization and shopping carts, and addresses privacy concerns related to first and third-party tracking cookies. It also mentions different approaches to maintaining state.

HTTP cookies: comments

What cookies can be used for:
• authorization
• shopping carts
• recommendations
• user session state (Web e-mail)

cookies and privacy:
• cookies permit sites to
learn a lot about you on
their site.
• third party persistent
cookies (tracking cookies)
allow common identity
(cookie value) to be
tracked across multiple
web sites

Challenge: How to keep state?
• at protocol endpoints: maintain state at
sender/receiver over multiple
transactions
• in messages: cookies in HTTP messages
carry state

Application Layer: 2-35

---

## Page 36

> **Title:** Application Layer Overview (slides 36-70) | **Type:** diagram_explanation | **Concepts:** HTTP GET, HTTP reply, embedded ad, NY Times, AdX.com | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide provides an example of displaying a web page, specifically a NY Times page with an embedded ad, illustrating the sequence of HTTP GET requests and replies between the client, nytimes.com, and AdX.com.

Example: displaying a NY Times web page

nytimes.com

AdX.com

1. HTTP
GET
2. HTTP reply


NY times page with embedded ad displayed

1. GET base html file from nytimes.com
3. fetch ad from AdX.com
5. display composed page
---

### Table 1

|  |
| --- |
|  |
|  |

### Table 2

|  |
| --- |
|  |
|  |

---

## Page 37

> **Title:** Application Layer Overview (slides 36-70) | **Type:** diagram_explanation | **Concepts:** cookies, tracking, first party cookie, third party cookie, Set-cookie, Referrer header | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide explains how cookies are used to track user browsing behavior, distinguishing between "first party" cookies from visited websites and "third party" cookies from unvisited ad websites.

nytimes.com (sports)

AdX.com

1634: sports, 2/15/22

NY Times: 1634

7493: NY Times sports, 2/15/22

HTTP

reply

Set cookie: 1634


HTTP GET
Referrer: NY Times Sports

HTTP reply
Set cookie: 7493

HTTP

GET

AdX: 7493

Cookies: tracking a user’s browsing behavior

“first party” cookie –
from website you chose 
to visit (provides base 
html file)

“third party” cookie –
from website you did not
choose to visit

### Table 1

|  |
| --- |
|  |
|  |

---

## Page 38

> **Title:** Application Layer Overview (slides 36-70) | **Type:** diagram_explanation | **Concepts:** cookies, third-party tracking, AdX.com, browsing history, targeted ads | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide further illustrates third-party cookie tracking, showing how AdX.com uses a cookie to track a user's browsing across multiple sites and return targeted ads based on their history.

Cookies: tracking a user’s browsing behavior

nytimes.com

AdX.com

1634: sports, 2/15/22

NY Times: 1634

7493: NY Times sports, 2/15/22

AdX: 7493

socks.com

HTTP

GET



HTTP GET
Referrer: socks.com, cookie: 7493

HTTP reply
Set cookie: 7493

7493: socks.com, 2/16/22

AdX:

tracks my web browsing

over sites with AdX ads
can return targeted ads

based on browsing history

### Table 1

|  |
| --- |
|  |
|  |

### Table 2

|  |  |
| --- | --- |
|  |  |

---

## Page 39

> **Title:** Application Layer Overview (slides 36-70) | **Type:** diagram_explanation | **Concepts:** cookies, third-party tracking, browsing history, targeted ads, first party cookies, third party cookies | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide demonstrates the persistence of cookie-based tracking, showing how a user's past browsing behavior with third-party cookies can lead to targeted ads even on a different site a day later.

Cookies: tracking a user’s browsing behavior (one day later)

nytimes.com (arts)

AdX.com

1634: sports, 2/15/22

NY Times: 1634

7493: NY Times sports, 2/15/22

AdX: 7493

socks.com


HTTP GET

Referrer: nytimes.com, cookie: 7493

HTTP reply
Set cookie: 7493

7493: socks.com, 2/16/22

cookie: 1634

HTTP

reply
HTTP

GET

Set cookie: 1634

1634: arts, 2/17/22

7493: NY Times arts, 2/15/22

Returned ad for socks!
---

### Table 1

|  |
| --- |
|  |
|  |

### Table 2

|  |
| --- |
|  |

---

## Page 40

> **Title:** Application Layer Overview (slides 36-70) | **Type:** summary | **Concepts:** cookies, user behavior tracking, first party cookies, third party cookies, privacy, invisible link, browser settings, Firefox, Safari, Chrome | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide summarizes the use of cookies for tracking user behavior, differentiating between first and third-party cookies, and notes the increasing browser-level disabling of third-party tracking cookies.

Cookies: tracking a user’s browsing behavior

Cookies can be used to:

• track user behavior on a given website (first party cookies)
• track user behavior across multiple websites (third party cookies)

without user ever choosing to visit tracker site (!)

• rather than displayed ad triggering HTTP GET to tracker, could be an invisible link

Third party tracking via cookies:

• disabled by default in Firefox, Safari browsers
• to be disabled in Chrome browser in 2023

---

## Page 41

> **Title:** Application Layer Overview (slides 36-70) | **Type:** concept | **Concepts:** GDPR, cookies, online identifiers, personal data, user control, privacy policy | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide discusses the implications of GDPR on cookies, stating that cookies are considered personal data when they can identify an individual, requiring explicit user control over their activation.

GDPR (EU General Data Protection Regulation) and cookies

“Natural persons may be associated with online 
identifiers […] such as internet protocol addresses, 
cookie identifiers or other identifiers […].

This may leave traces which, in particular when 
combined with unique identifiers and other 
information received by the servers, may be used to 
create profiles of the natural persons and identify 
them.”

GDPR, recital 30 (May 2018)

User has explicit control over

whether or not cookies are
when cookies can identify an individual, cookies

are considered personal data, subject to GDPR
personal data regulations
---

### Extracted from Image (OCR)

Jimn's laptop homepage
×
Accueil I Inria
×
+
8https:/www.inria.fr/fr
Inria
Institut national de recherche en sciences et technologies du
numérique
It
This site uses cookies and gives you control over what you want to activate
Privacy policy
OK, accept all
Deny all cookies
Personalize
Jimn's laptop homepage
×
Accueil I Inria
×
+
https:/www.inria.fr/fr
Inria
Institut national de recherche en sciences et technologies du
numérique
It
This site uses cookies and gives you control over what you want to activate
Privacy policy
OK, accept all
Deny all cookies
Personalize

---

## Page 42

> **Title:** Application Layer Overview (slides 36-70) | **Type:** definition | **Concepts:** Web cache, local Web cache, HTTP requests, origin server, client requests, object caching | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide defines a Web cache as a component that intercepts HTTP requests, serving objects from its cache if available or fetching and caching them from the origin server otherwise, to satisfy client requests efficiently.

Web caches

• user configures browser to point to a (local) Web cache
• browser sends all HTTP requests to cache

• if object in cache: cache returns object to client
• else cache requests object from origin server, caches received object, then returns object to client

Goal: satisfy client requests without involving origin server

client

Web cache

client

origin server

Application Layer: 2-42
---

### Table 1

| Web caches |  |  |  |
| --- | --- | --- | --- |
|  | Goal: satisfy client requests without involving origin server |  |  |
|  user configures browser to |  |  |  |
|  |  |  |  |
| point to a (local) Web cache |  | Web |  |
|  |  | cache |  |
|  |  |  |  |
|  browser sends all HTTP | client |  | origin |
|  |  |  | server |
| requests to cache |  |  |  |
| • if object in cache: cache |  |  |  |
| returns object to client |  |  |  |
| • else cache requests object |  |  |  |
|  | client |  |  |
| from origin server, caches |  |  |  |
| received object, then |  |  |  |
| returns object to client |  |  |  |
|  |  |  | Application Layer: 2-42 |

---

## Page 43

> **Title:** Application Layer Overview (slides 36-70) | **Type:** concept | **Concepts:** Web cache, proxy server, server for client, client to origin server, reduce response time, reduce traffic, Internet caches, content delivery, Cache-Control header | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide explains that web caches, also known as proxy servers, act as intermediaries to reduce client response time, decrease network traffic, and improve content delivery, with caching behavior controlled by server headers.

Web caches (aka proxy servers)

• Web cache acts as both
  • server for original requesting client
  • client to origin server

Why Web caching?
• reduce response time for client request
  • cache is closer to client
• reduce traffic on an institution’s access link
• Internet is dense with caches
• enables “poor” content providers to more effectively deliver content

• server tells cache about object’s allowable caching in response header:

Application Layer: 2-43
---

### Extracted from Image (OCR)

Cache-Control: max-age=<seconds>
Cache-Control: no-cache

---

## Page 44

> **Title:** Application Layer Overview (slides 36-70) | **Type:** numerical_example | **Concepts:** caching, access link rate, RTT, web object size, request rate, data rate, access link utilization, LAN utilization, end-end delay, queueing delays | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide presents a caching example scenario, outlining network parameters and performance metrics like link utilization and end-to-end delay, highlighting the problem of large queueing delays at high access link utilization.

Caching example

origin
servers
public
Internet

institutional

network
1 Gbps LAN

1.54 Mbps
access link
Performance:
• access link utilization = .97
• LAN utilization: .0015
• end-end delay = Internet delay + access link delay + LAN delay
= 2 sec + minutes + usecs

Scenario:
• access link rate: 1.54 Mbps
• RTT from institutional router to server: 2 sec
• web object size: 100K bits
• average request rate from browsers to origin servers: 15/sec
• avg data rate to browsers: 1.50 Mbps

problem: large queueing delays at high utilization!

Application Layer: 2-44

### Table 1

| Caching example |  |  |  |
| --- | --- | --- | --- |
| Scenario: |  |  |  |
|  | access link rate: 1.54 Mbps |  |  |
|  |  |  | origin |
|  | RTT from institutional router to server: 2 sec |  | servers |
|  |  |  | public |
|  web object size: 100K bits |  |  |  |
|  |  |  | Internet |
|  | average request rate from browsers to origin |  |  |
|  | servers: 15/sec |  |  |
|  | 
avg data rate to browsers: 1.50 Mbps |  |  |
|  |  |  | 1.54 Mbps |
|  |  |  | access link |
| Performance: |  |  |  |
|  | problem: large | institutional |  |
|  | access link utilization = .97 |  |  |
|  | queueing delays | network |  |
|  |  |  | 1 Gbps LAN |
|  | at high utilization!
LAN utilization: .0015 |  |  |
|  | end-end delay  =  Internet delay + |  |  |
|  | access link delay + LAN delay |  |  |
|  | =  2 sec + minutes + usecs |  |  |
|  |  |  | Application Layer: 2-44 |

---

## Page 45

> **Title:** Application Layer Overview (slides 36-70) | **Type:** numerical_example | **Concepts:** faster access link, performance improvement, access link utilization, end-end delay, cost | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide explores the option of buying a faster access link to improve network performance, showing how it reduces utilization and delay, but notes its high cost.

Performance:
• access link utilization = 0.97
• LAN utilization: 0.0015
• end-end delay = Internet delay + access link delay + LAN delay
= 2 sec + minutes + usecs

Option 1: buy a faster access link

origin
servers
public
Internet

institutional

network
1 Gbps LAN

1.54 Mbps access link

Scenario:
• access link rate: 1.54 Mbps
• RTT from institutional router to server: 2 sec
• web object size: 100K bits
• average request rate from browsers to origin servers: 15/sec
• avg data rate to browsers: 1.50 Mbps
154 Mbps
154 Mbps
0.0097
msecs
Cost: faster access link (expensive!)

Application Layer: 2-45
---

### Table 1

| Option 1: buy a faster access link |  |  |
| --- | --- | --- |
| Scenario:
154 Mbps |  |  |
| 
access link rate: 1.54 Mbps |  |  |
|  |  | origin |
| 
RTT from institutional router to server: 2 sec |  | servers |
|  |  | public |
|  web object size: 100K bits |  |  |
|  |  | Internet |
| 
average request rate from browsers to origin |  |  |
| servers: 15/sec |  |  |
|  |  |  |
| 
avg data rate to browsers: 1.50 Mbps |  | 154 Mbps |
|  |  | 1.54 Mbps |
|  |  | access link |
| Performance: |  |  |
|  | institutional |  |
| 
.0097
access link utilization = .97 |  |  |
|  | network |  |
|  |  | 1 Gbps LAN |
| 
LAN utilization: .0015 |  |  |
| 
end-end delay  =  Internet delay + |  |  |
| access link delay + LAN delay |  |  |
| =  2 sec + minutes + usecs |  |  |
| msecs |  |  |
| Cost: faster access link (expensive!) |  |  |
|  |  | Application Layer: 2-45 |

---

## Page 46

> **Title:** Application Layer Overview (slides 36-70) | **Type:** numerical_example | **Concepts:** web cache, local web cache, performance calculation, link utilization, end-end delay, cost | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide introduces installing a web cache as an alternative solution to improve network performance, posing questions on how to calculate its impact on link utilization and end-to-end delay, noting its low cost.

Performance:
• LAN utilization: ?
• access link utilization = ?
• average end-end delay = ?

Option 2: install a web cache

origin
servers
public
Internet

institutional

network
1 Gbps LAN

1.54 Mbps
access link

Scenario:
• access link rate: 1.54 Mbps
• RTT from institutional router to server: 2 sec
• web object size: 100K bits
• average request rate from browsers to origin
servers: 15/sec
• avg data rate to browsers: 1.50 Mbps

How to compute link
utilization, delay?

Cost: web cache (cheap!)

local web cache

Application Layer: 2-46

### Table 1

| Option 2: install a web cache |  |  |  |
| --- | --- | --- | --- |
| Scenario: |  |  |  |
|  | access link rate: 1.54 Mbps |  |  |
|  |  |  | origin |
|  | RTT from institutional router to server: 2 sec |  | servers |
|  |  |  | public |
|  web object size: 100K bits |  |  |  |
|  |  |  | Internet |
|  | average request rate from browsers to origin |  |  |
|  | servers: 15/sec |  |  |
|  | 
avg data rate to browsers: 1.50 Mbps |  |  |
|  |  |  | 1.54 Mbps |
|  |  |  | access link |
| Cost: web cache (cheap!) |  |  |  |
|  |  | institutional |  |
|  |  | network |  |
|  |  |  |  |
| Performance: |  |  | 1 Gbps LAN |
|  | LAN utilization: .? |  |  |
|  | How to compute link |  |  |
|  | utilization, delay?
access link utilization = ? |  |  |
|  |  |  | local web cache |
|  | average end-end delay  = ? |  |  |
|  |  |  | Application Layer: 2-46 |

---

## Page 47

> **Title:** Application Layer Overview (slides 36-70) | **Type:** numerical_example | **Concepts:** cache hit rate, access link utilization, end-end delay calculation, delay reduction, cost effectiveness | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide demonstrates calculating access link utilization and end-to-end delay with a web cache, showing that a 40% cache hit rate significantly reduces both access link utilization and average end-to-end delay, making it a cheaper solution.

Calculating access link utilization, end-end delay with cache:

origin
servers
public
Internet

institutional

network
1 Gbps LAN

1.54 Mbps access link

local web cache

Suppose cache hit rate is 0.4:

• 40% requests served by cache, with low (msec) delay
• 60% requests satisfied at origin
• rate to browsers over access link = 0.6 * 1.50 Mbps = 0.9 Mbps
• access link utilization = 0.9/1.54 = 0.58 means low (msec) queueing delay at access link
• average end-end delay:
= 0.6 * (delay from origin servers) + 0.4 * (delay when satisfied at cache)
= 0.6 * 2.01 + 0.4 * ~msecs = ~ 1.2 secs

Lower average end-end delay than with 154 Mbps link (and cheaper too!)

Application Layer: 2-47

### Table 1

| Calculating access link utilization, end-end delay |  |  |
| --- | --- | --- |
| with cache: |  |  |
| suppose cache hit rate is 0.4: |  |  |
|  |  |  |
|  40% requests served by cache, with low |  | origin |
|  |  | servers |
| (msec) delay |  |  |
|  |  | public |
|  |  |  |
|  60% requests satisfied at origin |  | Internet |
| •
rate to browsers over access link |  |  |
| = 0.6 * 1.50 Mbps  =  .9 Mbps |  |  |
|  |  | 1.54 Mbps |
| •
access link utilization = 0.9/1.54 = .58 means |  |  |
|  |  | access link |
| low (msec) queueing delay at access link |  |  |
|  | institutional |  |
|  |  |  |
|  average end-end delay: | network |  |
|  |  | 1 Gbps LAN |
| = 0.6 * (delay from origin servers) |  |  |
| + 0.4 * (delay when satisfied at cache) |  |  |
| = 0.6 (2.01) + 0.4 (~msecs) = ~ 1.2 secs |  | local web cache |
|  | lower average end-end delay than with 154 Mbps link (and cheaper too!) |  |
|  |  | Application Layer: 2-47 |

---

## Page 48

> **Title:** Application Layer Overview (slides 36-70) | **Type:** diagram_explanation | **Concepts:** Conditional GET, browser caching, up-to-date cached version, object transmission delay, network resources, If-modified-since header, HTTP/1.0 304 Not Modified, HTTP/1.0 200 OK | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide explains Conditional GET, a browser caching mechanism that prevents re-sending objects if the client has an up-to-date version, using the 'If-modified-since' header and the '304 Not Modified' response.

Browser caching: Conditional GET

Goal: don’t send object if browser has up-to-date cached version

• no object transmission delay (or use of network resources)
client: specify date of browser-cached copy in HTTP request

If-modified-since: <date>
server: response contains no object if browser-cached copy is up-to-date:

HTTP/1.0 304 Not Modified

HTTP request msg
If-modified-since: <date>

HTTP response
HTTP/1.0 304 Not Modified

object not modified before <date>

HTTP request msg
If-modified-since: <date>

HTTP response
HTTP/1.0 200 OK

<data>

object modified after <date>

client
server

Application Layer: 2-48
---

### Table 1

| Browser caching: Conditional GET |  |  |  |
| --- | --- | --- | --- |
|  | client |  | server |
| Goal: don’t send object if browser |  |  |  |
|  |  | HTTP request msg |  |
| has up-to-date cached version |  |  | object |
|  |  | If-modified-since: <date> |  |
|  |  |  | not |
| • no object transmission delay (or use |  |  |  |
|  |  |  | modified |
|  |  |  |  |
| of network resources) |  | HTTP response |  |
|  |  |  | before |
|  |  | HTTP/1.0 |  |
|  |  |  | <date> |
|  |  |  |  |
|  client: specify date of browser- |  | 304 Not Modified |  |

---

## Page 49

> **Title:** Application Layer Overview (slides 36-70) | **Type:** concept | **Concepts:** HTTP/2, decreased delay, multi-object HTTP requests, HTTP1.1, pipelined GETs, single TCP connection, server responds in-order, FCFS, head-of-line (HOL) blocking, loss recovery, object transmission stall | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide introduces HTTP/2, highlighting its goal to decrease delay in multi-object requests compared to HTTP/1.1, which suffered from issues like head-of-line blocking and stalled transmissions due to in-order responses.

HTTP/2

Key goal: decreased delay in multi-object HTTP requests

HTTP1.1: introduced multiple, pipelined GETs over single TCP connection

• server responds in-order (FCFS: first-come-first-served scheduling) to
• GET requests
• with FCFS, small object may have to wait for transmission (head-of-line (HOL) blocking) behind large object(s)
• loss recovery (retransmitting lost TCP segments) stalls object transmission

Application Layer: 2-49

---

## Page 50

> **Title:** Application Layer Overview (slides 36-70) | **Type:** concept | **Concepts:** HTTP/2, RFC 7540, decreased delay, multi-object HTTP requests, transmission order, client-specified object priority, push unrequested objects, frames, mitigate HOL blocking | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide details HTTP/2's features designed to reduce delay in multi-object requests, including flexible transmission order based on client-specified priority, the ability to push unrequested objects, and frame division to mitigate head-of-line blocking.

HTTP/2

HTTP/2: [RFC 7540, 2015] increased flexibility at server in sending objects to client:

• methods, status codes, most header fields unchanged from HTTP 1.1
• transmission order of requested objects based on client-specified object priority (not necessarily FCFS)
• push unrequested objects to client
• divide objects into frames, schedule frames to mitigate HOL blocking

Key goal: decreased delay in multi-object HTTP requests

Application Layer: 2-50

---

## Page 51

> **Title:** Application Layer Overview | **Type:** diagram_explanation | **Concepts:** HTTP 1.1, Head-of-Line blocking, object delivery | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide illustrates Head-of-Line (HOL) blocking in HTTP 1.1, where smaller objects must wait for a larger object (O1) to be delivered, even if they are requested earlier. It depicts a client requesting multiple objects from a server, showing the sequential delivery due to HOL blocking.

HTTP/2: mitigating HOL blocking

HTTP 1.1: client requests 1 large object (e.g., video file) and 3 smaller objects

client

server

GET O1
GET O2
GET O3
GET O4

O1 O2

O3 O4

object data requested

O1

O2
O3
O4

objects delivered in order requested: O2, O3, O4 wait behind O1
Application Layer: 2-51

### Table 1

| HTTP/2: mitigating HOL blocking |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | HTTP 1.1: client requests 1 large object (e.g., video file) and 3 smaller |  |  |  |  |  |  |  |
| objects |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  | server |  |  |
|  |  | GET O4 |  |  |  |  |  |  |
|  |  |  | GET O3 |  |  |  |  |  |
|  |  |  |  | GET O2 |  |  |  |  |
|  |  |  |  |  | GET O1 |  | object data requested |  |
|  | client |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  | O1 |  |
|  |  |  |  |  |  |  | O2 |  |
|  |  |  |  |  |  |  |  |  |
|  | O1 O2 |  |  |  |  |  | O3 |  |
|  |  |  |  |  |  |  | O4 |  |
|  | O3O4 |  |  |  |  |  |  |  |
|  |  | objects delivered in order requested: O2, O3, O4 wait behind O1 |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | Application Layer: 2-51 |

---

## Page 52

> **Title:** Application Layer Overview | **Type:** diagram_explanation | **Concepts:** HTTP/2, Head-of-Line blocking mitigation, frame transmission, interleaving | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide demonstrates how HTTP/2 mitigates Head-of-Line blocking by dividing objects into frames and interleaving their transmission. This allows smaller objects (O2, O3, O4) to be delivered quickly, even if a larger object (O1) is still being transmitted.

HTTP/2: mitigating HOL blocking

HTTP/2: objects divided into frames, frame transmission interleaved

client

server

GET O1
GET O2
GET O3
GET O4

O2

O4

object data requested

O1

O2
O3
O4

O2, O3, O4 delivered quickly, O1 slightly delayed

O3

O1

Application Layer: 2-52

### Table 1

| HTTP/2: mitigating HOL blocking |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | HTTP/2: objects divided into frames, frame transmission interleaved |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  | server |  |  |
|  |  |  | GET O4 |  |  |  |  |  |  |
|  |  |  |  | GET O3 |  |  |  |  |  |
|  |  |  |  |  | GET O2 |  |  |  |  |
|  |  |  |  |  |  | GET O1 |  | object data requested |  |
|  |  | client |  |  |  |  |  |  |  |
| O2 |  |  |  |  |  |  |  |  |  |
| O4 |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  | O3 |  |  |  |  |  |  | O1 |  |
|  |  |  |  |  |  |  |  | O2 |  |
|  |  |  |  |  |  |  |  | O3 |  |
|  |  |  |  |  |  |  |  | O4 |  |
|  |  | O1 |  |  |  |  |  |  |  |
|  |  |  | O2, O3, O4 delivered quickly, O1 slightly delayed |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  | Application Layer: 2-52 |

---

## Page 53

> **Title:** Application Layer Overview | **Type:** concept | **Concepts:** HTTP/2 limitations, HTTP/3, TCP, UDP, packet loss, congestion control, security | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide outlines the limitations of HTTP/2 over a single TCP connection, such as stalled transmissions due to packet loss and the lack of inherent security. It introduces HTTP/3 as a solution that adds security and per-object error/congestion control by running over UDP.

HTTP/2 to HTTP/3

HTTP/2 over single TCP connection means:
• recovery from packet loss still stalls all object transmissions

• as in HTTP 1.1, browsers have incentive to open multiple parallel 
TCP connections to reduce stalling, increase overall throughput
• no security over vanilla TCP connection
• HTTP/3: adds security, per object error- and congestion-
control (more pipelining) over UDP

Application Layer: 2-53

---

## Page 54

> **Title:** Application Layer Overview | **Type:** definition | **Concepts:** QUIC, UDP, HTTP/2, HTTP/3, Google | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide defines QUIC (Quick UDP Internet Connections) as an application-layer protocol built on UDP, designed to increase HTTP performance and used by Google. It illustrates the protocol stack comparison between HTTP/2 over TCP and HTTP/3 (HTTP/2 over QUIC over UDP).

• application-layer protocol, on top of UDP

• increase performance of HTTP
• deployed on many Google servers, apps (Chrome, mobile YouTube app)

QUIC: Quick UDP Internet Connections

IP

TCP

TLS

HTTP/2

IP

UDP

QUIC

HTTP/2 (slimmed)

Network

Transport

Application

HTTP/2 over TCP

HTTP/3

HTTP/2 over QUIC over UDP

Application Layer: 2-54
---

### Table 1

| QUIC: Quick UDP Internet Connections |  |  |  |  |
| --- | --- | --- | --- | --- |
|  |  application-layer protocol, on top of UDP |  |  |  |
| • increase performance of HTTP |  |  |  |  |
|  | • deployed on many Google servers, apps (Chrome, mobile YouTube app) |  |  |  |
|  |  | HTTP/2 (slimmed) |  |  |
|  | HTTP/2 |  |  |  |
| Application |  |  | HTTP/3 |  |
|  |  | QUIC |  |  |
|  | TLS |  |  |  |
| Transport | TCP |  |  |  |
|  |  | UDP |  |  |
| Network | IP | IP |  |  |
|  |  | HTTP/2 over QUIC over UDP |  |  |
|  | HTTP/2 over TCP |  |  |  |
|  |  |  |  | Application Layer: 2-54 |

---

## Page 55

> **Title:** Application Layer Overview | **Type:** concept | **Concepts:** QUIC, connection establishment, error control, congestion control, RTT | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide explains that QUIC incorporates well-known TCP algorithms for error and congestion control. It highlights QUIC's efficient connection establishment, which can set up reliability, congestion control, authentication, encryption, and state in just one Round Trip Time.

QUIC: Quick UDP Internet Connections

adopts approaches we’ll study in chapter for connection establishment, error control, congestion control

• error and congestion control: “Readers familiar with TCP’s loss detection and congestion control will find algorithms here that parallel well-known TCP ones.” [from QUIC specification]
• connection establishment: reliability, congestion control, authentication, encryption, state established in one RTT

Application Layer: 2-55

---

## Page 56

> **Title:** Application Layer Overview | **Type:** comparison | **Concepts:** QUIC, TCP handshake, TLS handshake, connection establishment, RTT, reliability, congestion control, authentication, encryption | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide compares connection establishment in TCP with TLS to QUIC, showing that TCP and TLS require two serial handshakes to establish full state. In contrast, QUIC achieves all necessary state (reliability, congestion control, authentication, crypto) in a single 1-RTT handshake.

QUIC: Connection establishment

TCP handshake
(transport layer)

TLS handshake

(security)

TCP (reliability, congestion control
state) + TLS (authentication, crypto
state)

• 2 serial handshakes

data

data

QUIC: reliability, congestion control,
authentication, crypto state

• 1 handshake

Application Layer: 2-56

QUIC
1RTT handshake

### Table 1

| QUIC: Connection establishment |
| --- |
| TCP handshake |
| QUIC |
| (transport layer) |
| 1RTT handshake |
| data |
| TLS handshake |
| (security) |
| data |
| TCP (reliability, congestion control |
| QUIC:  reliability, congestion control, |
| state) + TLS (authentication, crypto |
| authentication, crypto state |
| state) |
|  1 handshake |
|  2 serial handshakes |
| Application Layer: 2-56 |

---

## Page 57

> **Title:** Application Layer Overview | **Type:** diagram_explanation | **Concepts:** QUIC, 0-RTT, connection establishment, TLS session ticket | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide details QUIC's 0-RTT connection establishment, where a client can use a previously issued and cached TLS session ticket from the server. This allows subsequent connections to proceed without an initial handshake delay, sending data immediately.

QUIC: 0-RTT Connection establishment

data

Application Layer: 2-57

TLS session ticket

sent by server, 
cached at client

end of first QUIC
connection

start of second 
QUIC connection 
Client uses last session 
ticket for encryption, 
authentication for new 
connection

0 RTT handshake delay

data

### Table 1

|  | QUIC: 0-RTT Connection establishment |  |  |
| --- | --- | --- | --- |
|  | TLS  session ticket |  |  |
|  | sent by server, |  |  |
|  | cached at client |  |  |
|  |  | data |  |
|  | end of first QUIC |  |  |
|  | connection |  |  |
| Client uses last session | start of second |  |  |
|  |  |  |  |
| ticket for encryption, | QUIC connection |  |  |
| authentication for new |  |  |  |
|  |  | data |  |
| connection |  |  |  |
|  0 RTT handshake delay |  |  |  |
|  |  |  | Application Layer: 2-57 |

---

## Page 58

> **Title:** Application Layer Overview | **Type:** summary | **Concepts:** Network applications, HTTP, E-mail, SMTP, IMAP, DNS, Video streaming, CDN, Socket programming | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide provides an overview of the topics covered in the Application Layer chapter, including principles of network applications, HTTP, E-mail protocols (SMTP, IMAP), DNS, video streaming, CDNs, and socket programming.

Application layer: overview

• Principles of network applications
• Web and HTTP
• E-mail, SMTP, IMAP
• The Domain Name System
• DNS
• video streaming and content distribution networks
• socket programming with UDP and TCP
• Application Layer: 2-58

### Extracted from Image (OCR)

9/E
A TOP-DOWN APPROACH

---

## Page 59

> **Title:** Application Layer Overview | **Type:** definition | **Concepts:** E-mail, user agents, mail servers, SMTP, mail reader, user mailbox, message queue | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide introduces the three main components of email: user agents, mail servers, and SMTP. It defines a user agent as a mail reader for composing and reading messages, with outgoing and incoming mail stored on a server.

E-mail

Three major components:

• user agents
• mail servers
• simple mail transfer protocol: SMTP

User Agent

• a.k.a. “mail reader”
• composing, editing, reading mail messages
• e.g., Outlook, iPhone mail client
• outgoing, incoming messages stored on

server
user mailbox

outgoing 
message queue

SMTP

### Table 1

| E-mail |  |  |  |  |
| --- | --- | --- | --- | --- |
|  |  | user |  |  |
|  |  | agent |  |  |
| Three major components: | mail |  |  |  |
|  |  |  |  | user |
|  | server |  |  |  |
|  |  |  |  |  |
|  user agents |  |  |  | agent |
|  |  | SMTP |  |  |
|  mail servers |  |  | mail | user |
|  |  |  | server | agent |
|  simple mail transfer protocol: SMTP |  |  |  |  |
|  | SMTP |  |  |  |
|  |  |  |  | user |
|  |  | SMTP |  |  |
|  |  |  |  |  |
| User Agent | mail |  |  | agent |
|  | server |  |  |  |
|  a.k.a. “mail reader” |  |  |  |  |
|  |  | user |  |  |
|  |  |  |  |  |
|  composing, editing, reading mail messages |  | agent |  |  |
|  | user |  |  |  |
|  e.g., Outlook, iPhone mail client |  |  |  |  |
|  | agent |  |  |  |
|  |  |  |  | outgoing |
|  outgoing, incoming messages stored on |  |  |  |  |
|  |  |  |  | message queue |
| server |  |  |  | user mailbox |
|  |  |  |  | Application Layer: 2-59 |

---

## Page 60

> **Title:** Application Layer Overview | **Type:** concept | **Concepts:** Mail servers, mailbox, message queue, SMTP protocol, client-server | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide details the functions of mail servers, which include maintaining a mailbox for incoming messages and a message queue for outgoing mail. It also clarifies that SMTP protocol is used between mail servers, where the sending server acts as the client and the receiving server acts as the server.

E-mail: mail servers

user mailbox

outgoing message queue

mail server

mail server

mail server

SMTP

SMTP

SMTP

user agent

user agent

user agent

user agent

user agent

user agent

user agent

mail servers:
• mailbox contains incoming messages for user
• message queue of outgoing (to be sent) mail messages
SMTP protocol between mail servers to send email messages
• client: sending mail server
• "server": receiving mail server

Application Layer: 2-60

### Table 1

| E-mail: mail servers |  |  |  |  |
| --- | --- | --- | --- | --- |
|  |  | user |  |  |
|  |  | agent |  |  |
| mail servers: | mail |  |  |  |
|  |  |  |  | user |
|  | server |  |  |  |
|  |  |  |  | agent |
|  mailbox contains incoming |  |  |  |  |
|  |  | SMTP |  |  |
|  |  |  |  |  |
| messages for user |  |  | mail | user |
|  |  |  | server | agent |
|  message queue of outgoing (to be | SMTP |  |  |  |
| sent) mail messages |  |  |  |  |
|  |  |  |  | user |
|  |  | SMTP |  |  |
|  |  |  |  | agent |
|  |  |  |  |  |
| SMTP protocol between mail | mail |  |  |  |
|  | server |  |  |  |
|  |  |  |  |  |
| servers to send email messages |  | user |  |  |
|  |  | agent |  |  |
|  client: sending mail server |  |  |  |  |
|  | user |  |  |  |
|  |  |  |  |  |
|  “server”: receiving mail server | agent |  |  |  |
|  |  |  |  | outgoing |
|  |  |  |  | message queue |
|  |  |  |  | user mailbox |
|  |  |  |  | Application Layer: 2-60 |

---

## Page 61

> **Title:** Application Layer Overview | **Type:** definition | **Concepts:** SMTP, RFC 5321, TCP, port 25, direct transfer, handshaking, command/response, ASCII, status codes | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide explains SMTP, defined in RFC 5321, noting its use of TCP on port 25 for reliable direct transfer between mail servers. It outlines the three phases of SMTP transfer (handshaking, message transfer, closure) and its command/response interaction using ASCII text and status codes.

SMTP RFC (5321)

• uses TCP to reliably transfer email message
  from client (mail server initiating connection) to server, port 25

• direct transfer: sending server (acting like client)
  to receiving server
• three phases of transfer

  • SMTP handshaking (greeting)
  • SMTP transfer of messages
  • SMTP closure
• command/response interaction (like HTTP)

  • commands: ASCII text
  • response: status code and phrase

initiate TCP connection

RTT time


250 Hello

HELO

### Table 1

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| SMTP RFC (5321) |  | “client”
SMTP server |  | “server”
SMTP server |
|  uses TCP to reliably transfer email message |  |  |  |  |
|  | initiate TCP |  |  |  |
| from client (mail server initiating |  |  |  |  |
|  | connection |  |  |  |
| connection) to server, port 25 |  | RTT |  |  |
|  | TCP connection |  |  |  |
|  direct transfer: sending server (acting like client) |  |  |  |  |
|  | initiated |  |  |  |
| to receiving server |  |  |  |  |
|  |  |  |  |  |
|  three phases of transfer |  |  |  |  |
|  |  | SMTP |  |  |
| • SMTP handshaking (greeting) |  |  | HELO |  |
|  |  | handshaking |  |  |
| • SMTP transfer of messages |  |  |  |  |
|  |  |  | 250 Hello |  |
| • SMTP closure |  |  |  |  |
|  command/response interaction (like HTTP) |  |  |  |  |
|  |  | SMTP |  |  |
|  |  |  |  |  |
| • commands: ASCII text |  | transfers |  |  |
| •
response: status code and phrase |  |  |  |  |
|  |  | time |  |  |
|  |  |  |  | Application Layer: 2-61 |

---

## Page 62

> **Title:** Application Layer Overview | **Type:** example | **Concepts:** E-mail delivery, Alice and Bob scenario, user agent, mail server, SMTP, TCP connection, mailbox | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide illustrates a six-step scenario where Alice sends an email to Bob, detailing the interactions between Alice's user agent, her mail server (acting as an SMTP client), Bob's mail server (acting as an SMTP server), and Bob's user agent to deliver and read the message.

Scenario: Alice sends e-mail to Bob

1) Alice uses UA to compose e-mail

message “to” bob@someschool.edu

4) SMTP client sends Alice’s message

over the TCP connection

user
agent

mail
server

mail
server




Alice’s mail server
Bob’s mail server

user
agent

2) Alice’s UA sends message to her

mail server using SMTP; message 
placed in message queue

3) client side of SMTP at mail server

opens TCP connection with Bob’s mail 
server

5) Bob’s mail server places

the message in Bob’s 
mailbox

6) Bob invokes his user

agent to read message

Application Layer: 2-62
---

### Table 1

| Scenario: Alice sends e-mail to Bob |  |  |  |
| --- | --- | --- | --- |
|  |  | 4) SMTP client sends Alice’s message |  |
| 1) Alice uses UA to compose e-mail |  |  |  |
| message “to” bob@someschool.edu |  | over the TCP connection |  |
| 2) Alice’s UA sends message to her |  | 5) Bob’s mail server places |  |
| mail server using SMTP; message |  | the message in Bob’s |  |
| placed in message queue |  | mailbox |  |
| 3) client side of SMTP at mail server |  | 6) Bob invokes his user |  |
| opens TCP connection with Bob’s mail |  | agent to read message |  |
| server |  |  |  |
|  |  | user |  |
| user
1 | mail |  |  |
| mail |  |  |  |
|  |  | agent |  |
| agent | server |  |  |
| server |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
| Alice’s mail server |  |  |  |
|  | Bob’s mail server |  |  |
|  |  |  | Application Layer: 2-62 |

---

## Page 63

> **Title:** Application Layer Overview | **Type:** syntax/code | **Concepts:** SMTP interaction, HELO, MAIL FROM, RCPT TO, DATA, QUIT, status codes | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide presents a sample SMTP interaction, demonstrating the sequence of client commands (HELO, MAIL FROM, RCPT TO, DATA, QUIT) and corresponding server responses with status codes during an email transfer.

Sample SMTP interaction

S: 220 hamburger.edu
C: HELO crepes.fr
S: 250 Hello crepes.fr, pleased to meet you
C: MAIL FROM: <alice@crepes.fr>
S: 250 alice@crepes.fr... Sender ok
C: RCPT TO: <bob@hamburger.edu>
S: 250 bob@hamburger.edu... Recipient ok
C: DATA
S: 354 Enter mail, end with "." on a line by itself
C: Do you like ketchup?
C: How about pickles?
C: .
S: 250 Message accepted for delivery
C: QUIT
S: 221 hamburger.edu closing connection

Application Layer: 2-63
---

---

## Page 64

> **Title:** Application Layer Overview | **Type:** comparison | **Concepts:** SMTP, HTTP, persistent connections, 7-bit ASCII, CRLF.CRLF, client pull, client push, command/response, status codes, object encapsulation | **Chapter:** Application Layer Overview | **Exam Signal:** Yes
> **Summary:** This slide provides observations about SMTP, noting its use of persistent connections, 7-bit ASCII messages, and CRLF.CRLF to mark the end of a message. It then compares SMTP to HTTP, highlighting differences like client push versus client pull, and how objects are handled in response messages.

SMTP: observations

• SMTP uses persistent connections
• SMTP requires message (header & body) to be in 7-bit ASCII
• SMTP server uses CRLF.CRLF to determine end of message

Comparison with HTTP:

• HTTP: client pull
• SMTP: client push

• Both have ASCII command/response interaction, status codes

• HTTP: each object encapsulated in its own response message
• SMTP: multiple objects sent in multipart message

Application Layer: 2-64

---

## Page 65

> **Title:** Application Layer Overview | **Type:** definition | **Concepts:** Mail message format, SMTP, RFC 5321, RFC 2822, header, body, ASCII characters, MAIL FROM, RCPT TO | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide clarifies that SMTP (RFC 5321) is the protocol for exchanging email messages, while RFC 2822 defines the message format itself, consisting of header lines and a body separated by a blank line. It also differentiates between message header fields (like To, From, Subject) and SMTP commands.

Mail message format

SMTP: protocol for exchanging e-mail messages, defined in RFC 5321 (like RFC 7231 defines HTTP)
RFC 2822 defines syntax for e-mail message itself (like HTML defines syntax for web documents)

header

body

blank

line

• header lines, e.g.
  • To:
  • From:
  • Subject:
these lines, within the body of the email message area different from SMTP MAIL FROM:, RCPT TO: commands!
• Body: the “message” , ASCII characters only

Application Layer: 2-65

### Table 1

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| these lines, within the body of the email 
message area different from SMTP MAIL FROM:, 
 Body: the “message” , ASCII characters only | header |  |  |  |
|  |  |  |  |  |
|  |  | body |  |  |
|  |  |  |  |  |

---

## Page 66

> **Title:** Application Layer Overview | **Type:** concept | **Concepts:** Mail access protocols, SMTP, IMAP, HTTP, message retrieval, message storage, POP | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide explains that SMTP handles the delivery and storage of email messages to the receiver's server, while mail access protocols are used for retrieval from that server. It highlights IMAP for managing messages stored on the server (retrieval, deletion, folders) and HTTP for web-based email clients.

Retrieving email: mail access protocols

sender’s e-mail

server

SMTP
SMTP

receiver’s e-mail

server

e-mail access

protocol

(e.g., IMAP,

HTTP)

user
agent

user
agent

SMTP: delivery/storage of e-mail messages to receiver’s server

mail access protocol: retrieval from server

• IMAP: Internet Mail Access Protocol [RFC 3501]: messages stored on server, IMAP provides retrieval, deletion, folders of stored messages on server

HTTP: gmail, Hotmail, Yahoo!Mail, etc. provides web-based interface on top of SMTP (to send), IMAP (or POP) to retrieve e-mail messages

Application Layer: 2-66
---

### Table 1

|  | Retrieving email: mail access protocols |
| --- | --- |
|  | e-mail access |
|  | user
user |
|  | SMTP
SMTP |
|  | protocol |
|  | agent
agent |
|  | (e.g., IMAP, |
|  | HTTP) |
|  | sender’s e-mail 
receiver’s e-mail |
|  | server
server |
|  SMTP: delivery/storage of e-mail messages to receiver’s server |  |
|  mail access protocol: retrieval from server |  |
| • | IMAP: Internet Mail Access Protocol [RFC 3501]: messages stored on server, IMAP |
|  | provides retrieval, deletion, folders of stored messages on server |
|  HTTP: gmail, Hotmail, Yahoo!Mail, etc. provides web-based interface on |  |
|  | top of STMP (to send), IMAP (or POP) to retrieve e-mail messages |
|  | Application Layer: 2-66 |

---

## Page 67

> **Title:** Application Layer Overview | **Type:** summary | **Concepts:** Network applications, HTTP, E-mail, SMTP, IMAP, DNS, Video streaming, CDN, Socket programming | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide provides an overview of the topics covered in the Application Layer chapter, including principles of network applications, HTTP, E-mail protocols (SMTP, IMAP), DNS, video streaming, CDNs, and socket programming.

Application Layer: Overview

• Principles of network applications
• Web and HTTP
• E-mail, SMTP, IMAP
• The Domain Name System
• DNS
• video streaming and content distribution networks
• socket programming with UDP and TCP

Application Layer: 2-67

### Extracted from Image (OCR)

9/E
A TOP-DOWN APPROACH

---

## Page 68

> **Title:** Application Layer Overview | **Type:** definition | **Concepts:** DNS, Domain Name System, IP address, hostname, distributed database, application-layer protocol | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide defines the Domain Name System (DNS) as a distributed, hierarchical database and an application-layer protocol used to map human-readable hostnames to IP addresses and vice versa. It emphasizes DNS as a core Internet function implemented at the application layer.

DNS: Domain Name System

people: many identifiers:

• SSN, name, passport #
• Internet hosts, routers:
	+ IP address (32 bit) - used for addressing datagrams
	+ “name”, e.g., cs.umass.edu - used by humans
Q: how to map between IP address and name, and vice versa ?

Domain Name System (DNS):
	+ distributed database implemented in hierarchy of many name servers
	+ application-layer protocol: hosts, DNS servers communicate to resolve names (address/name translation)

• note: core Internet function, implemented as application-layer protocol
• complexity at network’s “edge”

Application Layer: 2-68

---

## Page 69

> **Title:** Application Layer Overview | **Type:** concept | **Concepts:** DNS, centralized DNS, single point of failure, traffic volume, distant database, maintenance, scalability, hostname-to-IP-address translation, host aliasing, mail server aliasing, load distribution | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide discusses why DNS is not centralized, citing issues like single point of failure, traffic volume, and maintenance, and demonstrates its massive scale. It also outlines key DNS services, including hostname-to-IP address translation, host aliasing, mail server aliasing, and load distribution.

DNS: services, structure

Q: Why not centralize DNS?

• single point of failure
• traffic volume
• distant centralized database
• maintenance

DNS services:

• hostname-to-IP-address translation
• host aliasing

• canonical, alias names
• mail server aliasing
• load distribution

• replicated Web servers: many IP addresses correspond to one name

A: doesn’t scale!

• Comcast DNS servers alone: 600B DNS queries/day
• Akamai DNS servers alone: 2.2T DNS queries/day

Application Layer: 2-69

---

## Page 70

> **Title:** Application Layer Overview | **Type:** concept | **Concepts:** DNS, distributed database, queries per day, performance, decentralized, reliability, security | **Chapter:** Application Layer Overview | **Exam Signal:** No
> **Summary:** This slide characterizes DNS as a vast, humongous distributed database handling trillions of queries daily, highlighting its critical performance requirements. It underscores DNS's decentralized organization, which ensures reliability and security across millions of responsible entities.

Thinking about the DNS

humongous distributed database:

• ~ billion records, each simple

handles many trillions of queries/day:

• many more reads than writes
• performance matters: almost every

Internet transaction interacts with 
DNS - msecs count!
organizationally, physically decentralized:

• millions of different organizations

responsible for their records

“bulletproof”: reliability, security

Application Layer: 2-70

### Extracted from Image (OCR)

NOT SO
EASY

---

## Page 71

> **Title:** DNS and Socket Programming | **Type:** diagram_explanation | **Concepts:** DNS, hierarchical database, root server, TLD server, authoritative DNS server, DNS query | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide explains the distributed, hierarchical structure of DNS, illustrating how a client queries root, TLD (.com), and authoritative (amazon.com) servers sequentially to resolve the IP address for a hostname like www.amazon.com.

DNS: a distributed, hierarchical database

Client wants IP address for www.amazon.com; 1st approximation:

• client queries root server to find .com DNS server
• client queries .com DNS server to get amazon.com DNS server
• client queries amazon.com DNS server to get IP address for www.amazon.com

.com DNS servers
.org DNS servers
.edu DNS servers

Top Level Domain

Root DNS Servers
Root

nyu.edu
DNS servers

umass.edu
DNS servers

yahoo.com
DNS servers

amazon.com
DNS servers

pbs.org
DNS servers

Application Layer: 2-71

### Table 1

|  | DNS: a distributed, hierarchical database |  |  |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Root DNS Servers |  | Root |
|  | …
… |  |  |
|  |  |  |  |
| .com DNS servers | .org DNS servers | .edu DNS servers | Top Level Domain |
| … | … … | … |  |
| amazon.com | pbs.org | nyu.edu
umass.edu |  |
| yahoo.com |  |  |  |
|  |  |  | Authoritative |
| DNS servers | DNS servers | DNS servers
DNS servers |  |
| DNS servers |  |  |  |
| Client wants IP address for www.amazon.com; 1st approximation: |  |  |  |
|  |  client queries root server to find .com DNS server |  |  |
|  |  client queries .com DNS server to get amazon.com DNS server |  |  |
|  |  client queries amazon.com DNS server to get  IP address for www.amazon.com |  |  |
|  |  |  | Application Layer: 2-71 |

---

## Page 72

> **Title:** DNS and Socket Programming | **Type:** diagram_explanation | **Concepts:** Root DNS servers, TLD servers, authoritative DNS servers | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide provides a diagram illustrating the hierarchy of DNS servers, emphasizing the role of root DNS servers as the starting point for name resolution, followed by TLD and authoritative servers.

DNS: root name servers

• official, contact-of-last-resort by name servers that can not resolve name

Application Layer: 2-72

### Table 1

| Root DNS Servers |  |  |  |  |
| --- | --- | --- | --- | --- |
| .com DNS servers | .org DNS servers | .edu DNS servers |  |  |
| yahoo.com | amazon.com | pbs.org | nyu.edu | umass.edu |
| DNS servers | DNS servers | DNS servers | DNS servers | DNS servers |

---

## Page 73

> **Title:** DNS and Socket Programming | **Type:** definition | **Concepts:** Root DNS servers, contact-of-last-resort, DNSSEC, ICANN, logical root servers | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide defines root name servers as the ultimate point of contact for name resolution and crucial for Internet function, mentioning DNSSEC for security. It notes there are 13 logical root servers globally, managed by ICANN.

DNS: root name servers

• official, contact-of-last-resort by name
• servers that can not resolve name
• incredibly important Internet function
• Internet couldn’t function without it!
• DNSSEC – provides security (authentication, message integrity)

13 logical root name “servers” worldwide; each “server,” replicated many times

Application Layer: 2-73

• ICANN (Internet Corporation for Assigned Names and Numbers) manages root DNS domain

---

## Page 74

> **Title:** DNS and Socket Programming | **Type:** definition | **Concepts:** Top-Level Domain (TLD) servers, authoritative DNS servers, Network Solutions, Educause, hostname to IP mappings | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide defines Top-Level Domain (TLD) servers as responsible for domains like .com, .org, and country codes, with examples like Network Solutions and Educause. It also defines authoritative DNS servers as an organization's own servers providing definitive hostname-to-IP mappings.

Top-Level Domain, and authoritative servers

Top-Level Domain (TLD) servers:
responsible for .com, .org, .net, .edu, .aero, .jobs, .museums, and all top-level country domains, e.g.: .cn, .uk, .fr, .ca, .jp
Network Solutions: authoritative registry for .com, .net TLD
Educause: .edu TLD

authoritative DNS servers:
organization’s own DNS server(s), providing authoritative hostname to IP mappings for organization’s named hosts
can be maintained by organization or service provider

Application Layer: 2-74

### Table 1

| Root DNS Servers |  |  |  |  |
| --- | --- | --- | --- | --- |
| .com DNS servers | .org DNS servers | .edu DNS servers |  |  |
| yahoo.com | amazon.com | pbs.org | nyu.edu | umass.edu |
| DNS servers | DNS servers | DNS servers | DNS servers | DNS servers |

---

## Page 75

> **Title:** DNS and Socket Programming | **Type:** concept | **Concepts:** Local DNS name servers, DNS query, local cache, DNS hierarchy, ISP | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide explains that when a host makes a DNS query, it first goes to its local DNS server, which can respond from its cache or forward the request into the DNS hierarchy. It also notes that local DNS servers, typically provided by ISPs, are not strictly part of the hierarchical structure.

Local DNS name servers

• when host makes DNS query, it is sent to its local DNS server

• Local DNS server returns reply, answering:
  • from its local cache of recent name-to-address translation pairs (possibly out of date!)
  • forwarding request into DNS hierarchy for resolution
• each ISP has local DNS name server; to find yours:
  • MacOS: % scutil --dns
  • Windows: >ipconfig /all
• local DNS server doesn’t strictly belong to hierarchy

Application Layer: 2-75

---

## Page 76

> **Title:** DNS and Socket Programming | **Type:** diagram_explanation | **Concepts:** DNS name resolution, iterated query, root DNS server, local DNS server, TLD DNS server, authoritative DNS server | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide explains the iterated DNS name resolution process, where a contacted server replies with the name of another server to contact until the IP address is found. An example involving engineering.nyu.edu and gaia.cs.umass.edu illustrates the flow.

DNS name resolution: iterated query

Example: host at engineering.nyu.edu wants IP address for gaia.cs.umass.edu

Iterated query:

• contacted server replies
with name of server to contact
• “I don’t know this name,
but ask this server”
requesting host at
engineering.nyu.edu
gaia.cs.umass.edu
root DNS server
local DNS server
dns.nyu.edu
authoritative DNS server
dns.cs.umass.edu
TLD DNS server
Application Layer: 2-76

### Table 1

| DNS name resolution: iterated query |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
|  |  |  | root DNS server |  |  |
| Example: host at engineering.nyu.edu |  |  |  |  |  |
| wants IP address for gaia.cs.umass.edu |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  | TLD DNS server |
|  |  |  |  |  |  |
| Iterated query: |  |  |  |  |  |
|  |  |  |  |  |  |
|  contacted server replies |  |  |  |  |  |
|  |  |  |  |  |  |
| with name of server to |  |  |  |  |  |
|  | requesting host at | local DNS server |  |  |  |
|  |  |  |  |  |  |
| contact | engineering.nyu.edu | dns.nyu.edu |  |  |  |
|  |  |  |  |  | gaia.cs.umass.edu |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  “I don’t know this name, |  |  |  |  |  |
| but ask this server” |  |  |  |  |  |
|  |  |  |  |  | authoritative DNS server |
|  |  |  |  |  | dns.cs.umass.edu |
|  |  |  |  |  | Application Layer: 2-76 |

---

## Page 77

> **Title:** DNS and Socket Programming | **Type:** diagram_explanation | **Concepts:** DNS name resolution, recursive query, root DNS server, local DNS server, TLD DNS server, authoritative DNS server | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide describes the recursive DNS name resolution query, where the contacted name server takes on the burden of resolving the name. It also notes a potential heavy load at upper levels of the hierarchy.

DNS name resolution: recursive query

requesting host at

* engineering.nyu.edu
* gaia.cs.umass.edu

root DNS server

local DNS server

dns.nyu.edu


authoritative DNS server

dns.cs.umass.edu


TLD DNS server

Recursive query:

* puts burden of name resolution on contacted name server
* heavy load at upper levels of hierarchy?

Example: host at engineering.nyu.edu wants IP address for gaia.cs.umass.edu

Application Layer: 2-77

### Table 1

| DNS name resolution: recursive query |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
|  |  | root DNS server |  |  |  |
| Example: host at engineering.nyu.edu |  |  |  |  |  |
| wants IP address for gaia.cs.umass.edu |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
| Recursive query: |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  | TLD DNS server |
|  puts burden of name |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
| requesting host at
resolution on | local DNS server |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
| engineering.nyu.edu | dns.nyu.edu |  |  |  |  |
|  |  |  |  |  |  |
| contacted name |  |  |  |  | gaia.cs.umass.edu |
| server |  |  |  |  |  |
|  heavy load at upper |  |  |  |  |  |
|  |  |  | authoritative DNS server |  |  |
|  |  |  |  |  |  |
| levels of hierarchy? |  |  |  | dns.cs.umass.edu |  |
|  |  |  |  |  | Application Layer: 2-77 |

---

## Page 78

> **Title:** DNS and Socket Programming | **Type:** concept | **Concepts:** DNS caching, response time, cache entries timeout, TTL, TLD servers, best-effort name-to-address translation | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide discusses DNS caching, which improves response time by storing learned mappings. Cache entries have a time-to-live (TTL) and may become out-of-date if IP addresses change.

Caching DNS Information

• once (any) name server learns mapping, it caches mapping,
and immediately returns a cached mapping in response to a query

• caching improves response time
• cache entries timeout (disappear) after some time (TTL)
• TLD servers typically cached in local name servers
• cached entries may be out-of-date

• if named host changes IP address, may not be known Internet-wide until all TTLs expire!
• best-effort name-to-address translation!

Application Layer: 2-78

---

## Page 79

> **Title:** DNS and Socket Programming | **Type:** definition | **Concepts:** DNS records, resource records (RR), RR format, type=A, type=NS, type=CNAME, type=MX, hostname, IP address, domain, authoritative name server, alias name, canonical name, SMTP mail server | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide defines DNS as a distributed database storing resource records (RR) and details the format and types of these records, including A for hostname-to-IP, NS for authoritative name servers, CNAME for aliases, and MX for mail servers.

DNS records

DNS: distributed database storing resource records (RR)

type=NS

• name is domain (e.g., foo.com)
• value is hostname of authoritative name server for this domain

RR format: (name, value, type, ttl)

type=A

• name is hostname
• value is IP address

type=CNAME

• name is alias name for some “canonical” (the real) name
• value is canonical name

type=MX

• value is name of SMTP mail server associated with name

Application Layer: 2-79

---

## Page 80

> **Title:** DNS and Socket Programming | **Type:** diagram_explanation | **Concepts:** DNS protocol messages, DNS query, DNS reply, message header, identification, flags, questions, answer RRs, authority RRs, additional RRs | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide illustrates the common format for both DNS query and reply messages, highlighting fields such as identification, flags, and sections for questions, answers, authority, and additional records.

identification
flags

# questions

questions (variable # of questions)

# additional RRs
# authority RRs

# answer RRs

answers (variable # of RRs)

authority (variable # of RRs)

additional info (variable # of RRs)

2 bytes
2 bytes

DNS protocol messages

DNS query and reply messages, both have same format:

message header:
identification: 16 bit # for query,
flags:
• query or reply
• recursion desired
• recursion available
• reply is authoritative

Application Layer: 2-80

### Table 1

| identification | flags |  |
| --- | --- | --- |
| # questions | # answer RRs |  |
| # authority RRs | # additional RRs |  |
| questions (variable # of questions) |  |  |
| answers (variable # of RRs) |  |  |
| authority (variable # of RRs) |  |  |
| additional info (variable # of RRs) |  |  |

---

## Page 81

> **Title:** DNS and Socket Programming | **Type:** diagram_explanation | **Concepts:** DNS protocol messages, DNS query, DNS reply, name field, type field, RRs, authoritative servers, additional info | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide further elaborates on the DNS protocol message format, specifying the locations for query name/type fields, resource records in response, authoritative server records, and helpful additional information.

identification
flags

# questions

questions (variable # of questions)

# additional RRs
# authority RRs

# answer RRs

answers (variable # of RRs)

authority (variable # of RRs)

additional info (variable # of RRs)

2 bytes
2 bytes
DNS query and reply messages, both have same format:

name, type fields for a query

RRs in response to query

records for authoritative servers

additional “helpful” info that may

be used

DNS protocol messages

Application Layer: 2-81
---

### Table 1

|  | identification | flags |  |
| --- | --- | --- | --- |
|  | # questions | # answer RRs |  |
|  | # authority RRs | # additional RRs |  |
|  | questions (variable # of questions) |  |  |
|  |  |  |  |
|  | answers (variable # of RRs) |  |  |
|  |  |  |  |
|  | authority (variable # of RRs) |  |  |
|  |  |  |  |
|  | additional info (variable # of RRs) |  |  |
|  |  |  |  |

---

## Page 82

> **Title:** DNS and Socket Programming | **Type:** example | **Concepts:** DNS registration, DNS registrar, authoritative name server, NS RR, A RR, MX RR, .com TLD server | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide provides an example of how a new startup, "Network Utopia," registers its domain and configures DNS records by providing authoritative name server information to a registrar and creating local A and MX records.

Getting your info into the DNS

example: new startup “Network Utopia”

• register name networkuptopia.com at DNS registrar (e.g., Network Solutions)
• provide names, IP addresses of authoritative name server (primary and secondary)
• registrar inserts NS, A RRs into .com TLD server:
  (networkutopia.com, dns1.networkutopia.com, NS)
  (dns1.networkutopia.com, 212.212.212.1, A)
• create authoritative server locally with IP address 212.212.212.1
• type A record for www.networkutopia.com
• type MX record for networkutopia.com

Application Layer: 2-82

---

## Page 83

> **Title:** DNS and Socket Programming | **Type:** concept | **Concepts:** DNS security, DDoS attacks, root servers, TLD servers, traffic filtering, local DNS servers, spoofing attacks, DNS cache poisoning, RFC 4033, DNSSEC, authentication services | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide outlines key DNS security vulnerabilities, including DDoS attacks against root and TLD servers and spoofing attacks like cache poisoning, and notes DNSSEC (RFC 4033) for authentication.

DNS security

DDoS attacks

• bombard root servers with
• not successful to date
• traffic filtering
• local DNS servers cache IPs of TLD servers, allowing root server bypass
• bombard TLD servers
• potentially more dangerous

Spoofing attacks
• intercept DNS queries,
• returning bogus replies
• DNS cache poisoning
• RFC 4033: DNSSEC
• authentication services

Application Layer: 2-83

---

## Page 84

> **Title:** Application Layer Overview | **Type:** summary | **Concepts:** network applications, Web and HTTP, E-mail, SMTP, IMAP, The Domain Name System, P2P applications, video streaming, content distribution networks, socket programming, UDP, TCP | **Chapter:** Application Layer Overview | **Exam Signal:** Yes
> **Summary:** This slide provides an overview of application layer topics, including network application principles, Web (HTTP), E-mail (SMTP, IMAP), DNS, P2P applications, video streaming, content distribution networks, and socket programming with UDP and TCP.

Application layer: overview

• Principles of network applications
• Web and HTTP
• E-mail, SMTP, IMAP
• The Domain Name System
• DNS
• P2P applications
• video streaming and content distribution networks
• socket programming with UDP and TCP
Application Layer: 2-84

### Extracted from Image (OCR)

9/E
A TOP-DOWN APPROACH

---

## Page 85

> **Title:** DNS and Socket Programming | **Type:** concept | **Concepts:** video streaming, CDN, Internet bandwidth, Netflix, YouTube, Amazon Prime, scaling, heterogeneity, distributed, application-level infrastructure | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide contextualizes video streaming by highlighting its immense internet bandwidth consumption and the challenges of scaling to billions of users with diverse capabilities, pointing to distributed CDNs as a solution.

Video Streaming and CDNs: context

• stream video traffic: major consumer of Internet bandwidth
• Netflix, YouTube, Amazon Prime: 80% of residential ISP traffic (2020)
• challenge: scale - how to reach ~1B users?
• challenge: heterogeneity
• different users have different capabilities (e.g., wired versus mobile; bandwidth rich versus bandwidth poor)
• solution: distributed, application-level infrastructure

Application Layer: 2-85

### Extracted from Image (OCR)

NETFLIX
www.kankan.com
Akamai
You Tube

---

## Page 86

> **Title:** DNS and Socket Programming | **Type:** concept | **Concepts:** video, images, pixels, coding, redundancy, spatial coding, temporal coding | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide defines video as a sequence of images and explains how coding techniques, such as spatial and temporal coding, are used to reduce the number of bits required to encode an image by leveraging redundancy.

Multimedia: video

• video: sequence of images
displayed at constant rate
• e.g., 24 images/sec
• digital image: array of pixels
• each pixel represented by bits
• coding: use redundancy within and
between images to decrease # bits
used to encode image
• spatial (within image)
• temporal (from one image to
next)

spatial coding example: instead
of sending N values of same
color (all purple), send only two
values: color value (purple) and
number of repeated values (N)

frame i

frame i+1

temporal coding example:
instead of sending
complete frame at i+1,
send only differences from
frame i

Application Layer: 2-86

### Table 1

| spatial coding example: instead |
| --- |
| of sending N values of same |
| color (all purple), send only two |
| values: color  value (purple)  and |
| number of repeated values (N) |

### Table 2

|  coding: use redundancy within and |  |  |
| --- | --- | --- |
|  | frame i |  |
| between images to decrease # bits |  |  |
| used to encode image |  |  |
| • spatial (within image) | temporal coding example: |  |
|  | instead of sending |  |
|  |  |  |
| • temporal (from one image to | complete frame at i+1, |  |
|  | send only differences from |  |
|  |  |  |
| next) | frame i | frame i+1 |

---

## Page 87

> **Title:** DNS and Socket Programming | **Type:** definition | **Concepts:** video coding, CBR (constant bit rate), VBR (variable bit rate), MPEG 1, MPEG2, MPEG4 | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide further discusses video encoding by defining Constant Bit Rate (CBR) and Variable Bit Rate (VBR) video, illustrating how encoding rates can be fixed or change based on spatial and temporal coding, and provides examples using MPEG standards.

Multimedia: video

spatial coding example: instead of sending N values of same color (all purple), send only two values: color value (purple) and number of repeated values (N)

frame i

frame i+1

temporal coding example: instead of sending complete frame at i+1, send only differences from frame i

CBR: (constant bit rate): video

encoding rate fixed

VBR: (variable bit rate): video

encoding rate changes as amount of spatial, temporal coding changes

examples:

• MPEG 1 (CD-ROM) 1.5 Mbps
• MPEG2 (DVD) 3-6 Mbps
• MPEG4 (often used in Internet, 64Kbps – 12 Mbps)

Application Layer: 2-87

### Table 1

| spatial coding example: instead |
| --- |
| of sending N values of same |
| color (all purple), send only two |
| values: color  value (purple)  and |
| number of repeated values (N) |

### Table 2

| examples: |  | frame i |  |
| --- | --- | --- | --- |
| • MPEG 1 (CD-ROM) 1.5 Mbps |  |  |  |
| • MPEG2 (DVD) 3-6 Mbps |  |  |  |
|  |  | temporal coding example: |  |
|  |  |  |  |
| • MPEG4 (often used in | instead of sending |  |  |
|  |  | complete frame at i+1, |  |
|  |  |  |  |
| Internet,  64Kbps – 12 Mbps) |  | send only differences from | frame i+1 |
|  | frame i |  |  |

---

## Page 88

> **Title:** DNS and Socket Programming | **Type:** concept | **Concepts:** streaming stored video, video server, client, Internet, bandwidth variability, network congestion, packet loss, delay, video quality | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide introduces the simple scenario of streaming stored video and highlights the primary challenges, including fluctuating server-to-client bandwidth due to network congestion, and issues like packet loss and delay affecting video quality.

Main challenges:

• Server-to-client bandwidth will vary over time, with changing network congestion levels (in-house, access network, network core, video server)
• Packet loss, delay due to congestion will delay playout, or result in poor video quality

Streaming stored video

Simple scenario:

Video server
(Stored video)
Client

Internet

Application Layer: 2-88

### Table 1

| Streaming stored video |
| --- |
| simple scenario: |
| Internet |
| video server |
| client |
| (stored video) |
| Main challenges: |
|  server-to-client bandwidth will vary over time, with changing network |
| congestion levels (in house, access network, network core, video |
| server) |
|  packet loss, delay due to congestion will delay playout, or result in |
| poor video quality |
| Application Layer: 2-88 |

---

## Page 89

> **Title:** DNS and Socket Programming | **Type:** diagram_explanation | **Concepts:** streaming stored video, video recording, video sending, video receiving, video playout, network delay, streaming | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide visually explains the process of streaming stored video, showing the timeline from video recording and sending to client reception and playout, emphasizing that streaming allows the client to begin playing early parts while later parts are still being sent.

Streaming stored video

1. video recorded (e.g., 30 frames/sec)

2. video sent

streaming: at this time, client playing out early part of video, while server still sending later part of video

time

3. video received, played out at client (30 frames/sec)

network delay (fixed in this example)

Application Layer: 2-89

### Table 1

| Streaming stored video |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
|  | 2. video |  |  |  |  |
|  | sent |  |  |  |  |
| 1.
video |  |  |  | 3. video received, played out at client |  |
| recorded |  |  | (30 frames/sec) |  |  |
| (e.g., 30 |  |  |  |  |  |
|  |  |  |  | time |  |
|  |  | network delay |  |  |  |
| frames/sec) |  |  |  |  |  |
|  |  | (fixed in this |  |  |  |
|  |  | example) |  |  |  |
|  |  |  | streaming: at this time, client  playing out |  |  |
|  |  |  | early part of video, while server still sending |  |  |
|  |  | later part of video |  |  |  |
|  |  |  |  |  | Application Layer: 2-89 |

---

## Page 90

> **Title:** DNS and Socket Programming | **Type:** concept | **Concepts:** streaming stored video challenges, continuous playout constraint, variable network delays, jitter, client-side buffer, client interactivity, packet loss, retransmission | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide details the challenges of streaming stored video, including maintaining continuous playout despite variable network delays (jitter) necessitating client-side buffering, and managing client interactivity like pause and fast-forward, alongside packet loss.

Streaming stored video: challenges

• continuous playout constraint: during client video playout, playout timing must match original timing

• but network delays are variable (jitter), so will need client-side buffer to match continuous playout constraint
• other challenges:
  • client interactivity: pause, fast-forward, rewind, jump through video
  • video packets may be lost, retransmitted

Application Layer: 2-90

### Extracted from Image (OCR)

Buffering

---

## Page 91

> **Title:** DNS and Socket Programming | **Type:** diagram_explanation | **Concepts:** streaming stored video, playout buffering, client-side buffering, playout delay, network-added delay, delay jitter, constant bit rate video transmission, client video reception | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide explains playout buffering in streaming video, showing how client-side buffering and playout delay compensate for network-added delay and jitter to ensure continuous video playback.

Streaming stored video: playout buffering

constant bit rate video
transmission

time

variable
network

delay

client video

reception

constant bit rate video
playout at client

client playout

delay

buffered

video

• client-side buffering and playout delay: compensate for
network-added delay, delay jitter

Application Layer: 2-91


at t0, 6 chunks have arrived, 2 chunks have been played out, so the buffer has 4 chunks

t0
---

### Table 1

| Streaming stored video: playout buffering |  |  |  |  |
| --- | --- | --- | --- | --- |
|  | constant bit |  |  |  |
|  |  |  |  |  |
|  | rate video |  | client video |  |
|  |  |  | constant bit |  |
|  | transmission |  |  |  |
|  |  |  | reception |  |
|  |  |  | rate video |  |
|  |  |  | playout at client |  |
|  |  | variable |  |  |
|  |  | network |  |  |
|  |  | delay | buffered
video |  |
|  |  |  |  | time |
|  |  |  | t0 |  |
|  |  | client playout |  |  |
|  |  |  | at t0, 6 chunks have arrived, 2 chunks have |  |
|  |  | delay | been played out, so the buffer has 4 chunks |  |
|  | client-side buffering and playout delay: compensate for |  |  |  |
|  | network-added delay, delay jitter |  |  |  |
|  |  |  |  | Application Layer: 2-91 |

---

## Page 92

> **Title:** DNS and Socket Programming | **Type:** definition | **Concepts:** DASH (Dynamic, Adaptive Streaming over HTTP), video chunks, multiple encoding rates, CDN nodes, manifest file, client bandwidth estimation, adaptive streaming | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide introduces Dynamic, Adaptive Streaming over HTTP (DASH), explaining how servers segment video into multi-rate chunks stored in CDNs and how clients dynamically request chunks based on estimated bandwidth to adapt quality.

Streaming multimedia: DASH

server:

• divides video file into multiple chunks
• each chunk encoded at multiple different rates
• different rate encodings stored in different files
• files replicated in various CDN nodes
• manifest file: provides URLs for different chunks

client:

• periodically estimates server-to-client bandwidth
• consulting manifest, requests one chunk at a time
• chooses maximum coding rate sustainable given current bandwidth
• can choose different coding rates at different points in time (depending on available bandwidth at time), and from different servers

Dynamic, Adaptive Streaming over HTTP

Application Layer: 2-92

### Table 1

|  |  | Dynamic, Adaptive |  |  |
| --- | --- | --- | --- | --- |
| Streaming multimedia: DASH |  |  |  |  |
|  |  | Streaming over HTTP |  |  |
| server: |  |  |  |  |
|  divides video file into multiple chunks |  | ... |  |  |
|  |  |  |  |  |
|  each chunk encoded at multiple different rates | ... |  |  |  |
|  different rate encodings stored in different files |  |  |  |  |
|  |  |  | ? |  |
|  files replicated in various CDN nodes |  |  |  |  |
|  |  | ... |  |  |
|  |  |  |  |  |
|  manifest file: provides URLs for different chunks |  |  |  | client |

---

## Page 93

> **Title:** DNS and Socket Programming | **Type:** concept | **Concepts:** DASH, client intelligence, chunk request timing, encoding rate selection, server selection, streaming video components, encoding, playout buffering | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide highlights the client-side intelligence in DASH, where the client determines chunk request timing, encoding rate, and server location to optimize video quality and prevent buffer issues. It summarizes streaming video as a combination of encoding, DASH, and playout buffering.

ABSOLUTE RULES — VIOLATING ANY RULE IS FAILURE:
1. Output ONLY text that exists in the input. Do NOT invent, expand, or add ANY content.
2. Do NOT add explanations, notes, commentary, placeholders like "[Insert ...]", or examples.
3. Do NOT add "Note:", "Formula:", or any section that is not in the original.
4. Fix obvious OCR typos (e.g., "vl" → "v1", "lNT" → "INT") but NEVER guess meaning.
5. Remove garbage tokens: random hex strings, repeated symbols (*****, ====), stray characters.
6. Keep bullet points, headings, and structure from the original.
7. If the input is mostly a table, format it as a markdown table.
8. If the input is empty or only garbage, output exactly: [empty page]
9. Output ONLY the cleaned text. No preamble, no sign-off.

Streaming multimedia: DASH

• “intelligence” at client: client determines
	+ when to request chunk (so that buffer starvation, or overflow does not occur)
	+ what encoding rate to request (higher quality when more bandwidth available)
	+ where to request chunk (can request from URL server that is “close” to client or has high available bandwidth)

Streaming video = encoding + DASH + playout buffering

Application Layer: 2-93

### Table 1

| Streaming multimedia: DASH |  |  |  |  |
| --- | --- | --- | --- | --- |
| “intelligence” at client: client |  |  |  |  |
| determines |  | ... |  |  |
|  |  |  |  |  |
| • when to request chunk (so that buffer | ... |  |  |  |
| starvation, or overflow does not occur) |  |  |  |  |
|  |  |  | ? |  |
| • what encoding rate to request (higher |  |  |  |  |
|  |  | ... |  |  |
|  |  |  |  | client |
| quality when more bandwidth |  |  |  |  |
| available) |  |  |  |  |
| • where to request chunk (can request |  |  |  |  |
| from URL server that is “close” to |  |  |  |  |
| client or has high available |  |  |  |  |
| bandwidth) |  |  |  |  |
|  | Streaming video = encoding + DASH + playout buffering |  |  |  |
|  |  |  |  | Application Layer: 2-93 |

---

## Page 94

> **Title:** DNS and Socket Programming | **Type:** concept | **Concepts:** Content distribution networks (CDNs), streaming content, simultaneous users, single large mega-server, single point of failure, network congestion, scalability | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide introduces the challenge of streaming content to many simultaneous users and explains why a single, large "mega-server" is not a scalable solution due to risks like single points of failure and network congestion.

Content distribution networks (CDNs)

challenge: how to stream content (selected from millions of videos) to hundreds of thousands of simultaneous users?

• option 1: single, large “mega-server”

• single point of failure
• point of network congestion
• long (and possibly congested) path to distant clients

….quite simply: this solution doesn’t scale

Application Layer: 2-94

---

## Page 95

> **Title:** DNS and Socket Programming | **Type:** concept | **Concepts:** Content distribution networks (CDNs), multiple copies of videos, geographically distributed sites, enter deep, Akamai, bring home, Limelight, access networks, POPs | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide presents the CDN solution of storing and serving multiple video copies from geographically distributed sites, contrasting the "enter deep" approach with many servers close to users (Akamai) and the "bring home" approach with fewer, larger clusters (Limelight).

Content distribution networks (CDNs)

challenge: how to stream content (selected from millions of videos) to hundreds of thousands of simultaneous users?

• enter deep: push CDN servers deep into many access networks 
• close to users
• Akamai: 240,000 servers deployed 
in > 120 countries (2015)

• option 2: store/serve multiple copies of videos at multiple
geographically distributed sites (CDN)
• bring home: smaller number (10’s) of 
larger clusters in POPs near access nets
• used by Limelight

Application Layer: 2-95

### Extracted from Image (OCR)

Limelight
NETWORKS
Akamai

---

## Page 96

> **Title:** DNS and Socket Programming | **Type:** table | **Concepts:** Akamai, CDN, servers, hits per second, deliveries per day, terabits per second (peak), locations, networks, cities, countries | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide presents a table detailing the current scale of Akamai's CDN infrastructure, including its vast number of servers, daily hits, delivery capacity, and extensive global presence across locations, networks, cities, and countries.

Akamai today:

Transport Layer: 3-96

Source: https://networkingchannel.eu/living-on-the-edge-for-a-quarter-century-an-akamai-retrospective-downloads/

### Table 1

| The Akamai Edge Today |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
| 100+ | 7+ | 175+ |  |  |  |
| 360K |  |  |  |  |  |
| million hits | trillion | terabits per |  |  |  |
| servers | per second | deliveries | (250+ | second | peak) |
| per day |  |  |  |  |  |
| 4,200+ | 1,350+ | 840+ |  |  |  |
| locations | networks | cities | countries |  |  |

---

## Page 97

> **Title:** TCP Socket Programming and Protocols | **Type:** example | **Concepts:** Netflix, OpenConnect CDN nodes, content storage, subscriber request, manifest file, client retrieval, highest supportable rate, network congestion | **Chapter:** TCP Socket Programming and Protocols | **Exam Signal:** No
> **Summary:** This slide explains Netflix's content delivery, detailing how content copies are stored in OpenConnect CDN nodes, a manifest file guides clients to retrieve content, and clients adapt to network conditions by selecting the highest supportable rate.

How does Netflix work?

• subscriber requests content, service provider returns manifest
• Netflix: stores copies of content (e.g., Madmen) at its OpenConnect CDN nodes
• where's Madmen?
• manifest file
• using manifest, client retrieves content at highest supportable rate
• may choose different rate or copy if network path congested

Application Layer: 2-97

### Table 1

| How does Netflix work? |  |
| --- | --- |
|  Netflix: stores copies of content (e.g., MADMEN) at its |  |
| (worldwide)  OpenConnect CDN  nodes |  |
|  subscriber requests content, service provider returns manifest |  |
| • using manifest, client retrieves content at highest supportable rate |  |
| • may choose different rate or copy if network path congested |  |
| manifest file |  |
| where’s Madmen? |  |
|  | Application Layer: 2-97 |

---

## Page 98

> **Title:** DNS and Socket Programming | **Type:** concept | **Concepts:** Content distribution networks (CDNs), OTT (over the top), Internet host-host communication, CDN node content placement, content retrieval rate | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide delves into Content Distribution Networks (CDNs) and "Over The Top" (OTT) challenges, focusing on strategic decisions about content placement in CDN nodes and optimal content retrieval rates.

Internet host-host communication as a service

OTT challenges: coping with a congested Internet from the “edge”

• what content to place in which CDN node?
• from which CDN node to retrieve content? At which rate?

OTT: “over the top”

Content distribution networks (CDNs)

Application Layer: 2-98

### Table 1

| Content distribution networks (CDNs) |  |
| --- | --- |
| OTT: “over the top” |  |
| Internet host-host communication as a service |  |
| OTT challenges: coping with a congested Internet from the “edge” |  |
|  what content to place in which CDN node? |  |
|  from which CDN node to retrieve content? At which rate? |  |
|  | Application Layer: 2-98 |

---

## Page 99

> **Title:** Application Layer Overview | **Type:** summary | **Concepts:** network applications, Web and HTTP, E-mail, SMTP, IMAP, The Domain Name System, P2P applications, video streaming, content distribution networks, socket programming, UDP, TCP | **Chapter:** Application Layer Overview | **Exam Signal:** Yes
> **Summary:** This slide provides an overview of application layer topics, including network application principles, Web (HTTP), E-mail (SMTP, IMAP), DNS, P2P applications, video streaming, content distribution networks, and socket programming with UDP and TCP.

Application Layer: Overview

• Principles of network applications
• Web and HTTP
• E-mail, SMTP, IMAP
• The Domain Name System
DNS
• P2P applications
• video streaming and content distribution networks
• socket programming with UDP and TCP
Application Layer: 2-99

### Extracted from Image (OCR)

9/E
A TOP-DOWN APPROACH

---

## Page 100

> **Title:** DNS and Socket Programming | **Type:** definition | **Concepts:** Socket programming, client/server applications, sockets, application process, end-to-end transport protocol, operating system (OS), transport, app developer | **Chapter:** DNS and Socket Programming | **Exam Signal:** No
> **Summary:** This slide introduces socket programming with the goal of building client/server applications, defining a socket as a conceptual "door" between an application process and the end-to-end transport protocol. It notes that the OS controls the Internet layer while the app developer controls the transport.

Socket programming

goal: learn how to build client/server applications that communicate using sockets
socket: door between application process and end-to-end transport protocol
Internet controlled by OS
transport controlled by app developer
transport application physical link network process

### Table 1

| application
process
transport |  |
| --- | --- |
|  |  |
| network
link
physical |  |
|  |  |
|  |  |

### Table 2

| application
process
transport |
| --- |
| network |
| link |
| physical |

### Table 3

| application
process
transport |
| --- |
| network |
| link |
| physical |

---

## Page 101

> **Title:** DNS and Socket Programming (slides 71-105) | **Type:** concept | **Concepts:** Socket programming, UDP, TCP, Client-server interaction | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide introduces socket programming, differentiating between UDP and TCP, and outlines a client-server application example for character conversion.

Socket programming

Two socket types for two transport services:

• UDP: unreliable datagram
• TCP: reliable, byte stream-oriented

Application Example:

1. client reads a line of characters (data) from its keyboard and sends
data to server

2. server receives the data and converts characters to uppercase

3. server sends modified data to client

4. client receives modified data and displays line on its screen

Application Layer: 2-101

---

## Page 102

> **Title:** DNS and Socket Programming (slides 71-105) | **Type:** definition | **Concepts:** UDP, Unreliable datagram, No connection, Explicit addressing, Out-of-order data | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide details UDP socket programming, emphasizing its connectionless nature, explicit IP addressing, and unreliable transfer of datagrams which may be lost or received out-of-order.

Socket programming with UDP

UDP: no “connection” between
client and server:
• no handshaking before sending data
• sender explicitly attaches IP destination
address and port # to each packet
• receiver extracts sender IP address and
port# from received packet

UDP: transmitted data may be lost or received out-of-order

Application viewpoint:
• UDP provides unreliable transfer
of groups of bytes (“datagrams”)
between client and server processes

Application Layer: 2-102

---

## Page 103

> **Title:** DNS and Socket Programming (slides 71-105) | **Type:** diagram_explanation | **Concepts:** UDP socket interaction, Client socket, Server socket, Datagrams | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This diagram illustrates the client-server interaction model for UDP sockets, showing the creation of sockets, and the flow of sending and receiving datagrams.

Client/server socket interaction: UDP

close
clientSocket

read datagram from
clientSocket

create socket:
clientSocket = socket(AF_INET, SOCK_DGRAM)

Create datagram with serverIP address
And port=x; send datagram via
clientSocket

create socket, port= x:
serverSocket = socket(AF_INET, SOCK_DGRAM)

read datagram from
serverSocket

write reply to
serverSocket
specifying
client address,
port number

server (running on serverIP)
client

Application Layer: 2-103

---

## Page 104

> **Title:** DNS and Socket Programming (slides 71-105) | **Type:** syntax/code | **Concepts:** Python UDP client, socket, sendto, recvfrom, encode, decode | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide provides Python code for a UDP client, demonstrating how to create a socket, get user input, send encoded messages to a server, receive and decode replies, and close the socket.

Example app: UDP client

from socket import *
serverName = 'hostname'
serverPort = 12000
clientSocket = socket(AF_INET, SOCK_DGRAM)
message = input('Input lowercase sentence:')
clientSocket.sendto(message.encode(), (serverName, serverPort))
modifiedMessage, serverAddress = clientSocket.recvfrom(2048)
print(modifiedMessage.decode())
clientSocket.close()

Python UDPClient

include Python's socket library

create UDP socket

get user keyboard input

attach server name, port to message; send into socket

print out received string and close socket

read reply data (bytes) from socket

Application Layer: 2-104

---

## Page 105

> **Title:** DNS and Socket Programming (slides 71-105) | **Type:** syntax/code | **Concepts:** Python UDP server, socket, bind, recvfrom, sendto, upper() | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide presents Python code for a UDP server, illustrating how to create and bind a socket, receive messages from clients, convert them to uppercase, and send back modified replies.

Example app: UDP server

Python UDPServer

from socket import *
serverPort = 12000
serverSocket = socket(AF_INET, SOCK_DGRAM)
serverSocket.bind(('', serverPort))
print('The server is ready to receive')
while True:
    message, clientAddress = serverSocket.recvfrom(2048)
    modifiedMessage = message.decode().upper()
    serverSocket.sendto(modifiedMessage.encode(), clientAddress)

create UDP socket

bind socket to local port number 12000

loop forever

Read from UDP socket into message, getting client’s address (client IP and port)

send upper case string back to this client

Application Layer: 2-105

---

## Page 106

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** concept | **Concepts:** TCP socket programming, Connection-oriented, Reliable byte-stream, Client-server contact, Welcoming socket | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide explains TCP socket programming, emphasizing its reliable, in-order, byte-stream transfer and the connection establishment process where clients contact a server's welcoming socket.

Socket programming with TCP

Client must contact server

• server process must first be
running
• server must have created socket
(door) that welcomes client’s
contact

Client contacts server by:

• Creating TCP socket, specifying IP
address, port number of server
process
• when client creates socket: client
TCP establishes connection to
server TCP

• when contacted by client, server
TCP creates new socket for server
process to communicate with that
particular client

• allows server to talk with multiple
clients
• client source port # and IP address used
to distinguish clients (more in Chap 3)

TCP provides reliable, in-order
byte-stream transfer (“pipe”)
between client and server
processes

Application viewpoint

Application Layer: 2-106

---

## Page 107

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** diagram_explanation | **Concepts:** TCP socket interaction, Connection setup, serverSocket.accept(), clientSocket.connect() | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This diagram illustrates the client-server interaction for TCP sockets, detailing the connection setup, data exchange via connection sockets, and closing procedures.

Client/server socket interaction: TCP

server (running on hostid)
client

wait for incoming
connection request
connectionSocket = serverSocket.accept()

create socket,
port=x, for incoming 
request:
serverSocket = socket()

create socket,
connect to hostid, port=x
clientSocket = socket()

send request using
clientSocket
read request from
connectionSocket

write reply to
connectionSocket

TCP 
connection setup

close
connectionSocket

read reply from
clientSocket

close
clientSocket

Application Layer: 2-107
---

---

## Page 108

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** syntax/code | **Concepts:** Python TCP client, socket, connect, send, recv, close | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide provides Python code for a TCP client, demonstrating how to create a socket, connect to a server, send an encoded sentence, receive and print a modified sentence, and close the socket.

Example app: TCP client

from socket import *
serverName = 'servername'
serverPort = 12000
clientSocket = socket(AF_INET, SOCK_STREAM)
clientSocket.connect((serverName,serverPort))
sentence = input('Input lowercase sentence:')
clientSocket.send(sentence.encode())
modifiedSentence = clientSocket.recv(1024)
print ('From Server:', modifiedSentence.decode())
clientSocket.close()

Python TCPClient

create TCP socket for server, 
remote port 12000

Application Layer: 2-108

---

## Page 109

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** syntax/code | **Concepts:** Python TCP server, socket, bind, listen, accept, recv, send, close | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide presents Python code for a TCP server, illustrating how to create a welcoming socket, bind it, listen for requests, accept client connections, process data, and send capitalized replies before closing the client connection.

Example app: TCP server

from socket import *
serverPort = 12000
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind(('', serverPort))
serverSocket.listen(1)
print('The server is ready to receive')
while True:
    connectionSocket, addr = serverSocket.accept()
    sentence = connectionSocket.recv(1024).decode()
    capitalizedSentence = sentence.upper()
    connectionSocket.send(capitalizedSentence.encode())
    connectionSocket.close()

Python TCPServer

create TCP welcoming socket

server begins listening for incoming TCP requests

loop forever

server waits on accept() for incoming requests, new socket created on return

read bytes from socket (but not address as in UDP)

close connection to this client (but not welcoming socket)

Application Layer: 2-109

---

## Page 110

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** summary | **Concepts:** Application architectures, Client-server, P2P, TCP, UDP, HTTP, SMTP, IMAP, DNS, BitTorrent, Video streaming, CDNs, Socket programming | **Chapter:** CH2: Application Layer | **Exam Signal:** Yes
> **Summary:** This slide summarizes Chapter 2, covering application architectures, service requirements, Internet transport service models (TCP/UDP), specific protocols like HTTP, SMTP, IMAP, DNS, P2P, video streaming, CDNs, and socket programming.

Chapter 2: Summary

• application architectures
  • client-server
  • P2P
• application service requirements:
  • reliability, bandwidth, delay
• Internet transport service model
  • connection-oriented, reliable: TCP
  • unreliable, datagrams: UDP
• specific protocols:
  • HTTP
  • SMTP, IMAP
  • DNS
  • P2P: BitTorrent
• video streaming, CDNs
• socket programming:
  • TCP, UDP sockets

Application Layer: 2-110

---

## Page 111

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** summary | **Concepts:** Protocols, Client/server request/reply, Centralized vs. decentralized, Stateless vs. stateful, Scalability, Reliable vs. unreliable message transfer, Complexity at network edge | **Chapter:** CH2: Application Layer | **Exam Signal:** Yes
> **Summary:** This slide provides a second summary for Chapter 2, emphasizing the importance of protocols and key themes such as client/server interaction, centralized vs. decentralized systems, state management, scalability, and network edge complexity.

Chapter 2: Summary

Most importantly: learned about protocols!

Important themes:

• typical client/server request/reply message exchange
• centralized vs. decentralized
• stateless vs. stateful
• scalability
• reliable vs. unreliable message transfer
• “complexity at network edge”

Application Layer: 2-111

### Extracted from Image (OCR)

9/E
A TOP-DOWN APPROACH

---

## Page 112

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** other | **Concepts:** Timeouts, TRY/EXCEPT, RDT programming assignment, Socket programming assignment | **Chapter:** CH2: Application Layer | **Exam Signal:** Yes
> **Summary:** This slide serves as a note on additional Chapter 2 content, highlighting the importance of understanding timeouts and `TRY/EXCEPT` blocks for programming assignments, especially in RDT and socket programming.

Application Layer: 2-112

Additional Chapter 2 slides

JFK note: the timeout slides are important IMHO if one is doing a programming assignment (especially an RDT programming assignment in Chapter 3), since students will need to use timers in their code, and the TRY/EXCEPT is really the easiest way to do this. I introduce this here in Chapter 2 with the socket programming assignment since it teaches something (how to handle exceptions/timeouts), and lets students learn/practice that before doing the RDT programming assignment, which is harder
---

---

## Page 113

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** concept | **Concepts:** Waiting for multiple events, Timeout, select(), multithreading, settimeout(), socket(), connect(), send(), recv() | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide explains the need for socket programs to wait for multiple events, such as replies or timeouts, and lists Python socket functions relevant to implementing timeouts.

timeout

handle 
timeout

…

…
receive a message

Socket programming: waiting for multiple events

Application Layer: 2-113

• sometimes a program must wait for one of several events to happen, e.g.:
• wait for either (i) a reply from another end of the socket, or (ii) timeout: timer
• wait for replies from several different open sockets: select(), multithreading
• timeouts are used extensively in networking 
• using timeouts with Python socket:
  • socket()
  • connect()
  • send()
  • recv()
  • settimeout()

---

## Page 114

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** diagram_explanation | **Concepts:** socket.settimeout(), Timer, Timeout exception, s.recv() | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide illustrates how Python's `socket.settimeout()` works with diagrams, showing how a timer starts with `recv()` and raises a timeout exception if no message arrives within the specified duration.

Application Layer: 2-114

s.settimeout(30)
s.recv()

timer starts!

interrupt s.recv() &
raise timeout exception

timeout

s.settimeout(10)
s.recv()

timer starts!

receive a message
& timer stop!

s.recv()

timer starts!

interrupt s.recv() &
raise timeout exception

timeout

Set a timeout on all future socket operations of that specific socket!

no packet arrives in 30 secs

no packet arrives in 10 secs

How Python socket.settimeout() works?
---

---

## Page 115

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** definition | **Concepts:** Python try-except block, Exception handling, try block, except block | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide defines the Python `try-except` block, explaining its purpose in executing code and catching exceptions that may occur, thereby handling errors gracefully.

Execute a block of code, and handle “exceptions” that may occur when 
executing that block of code

Python try-except block

try:

<do something>

except <exception>:

<handle the exception>

Executing this try code block may cause exception(s) to catch. If an exception 
is raised, execution jumps directly into except code block

this except code block is only executed if an <exception> occurred in the try 
code block (note: except block is required with a try block)

---

## Page 116

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** syntax/code | **Concepts:** Socket timeouts, Python TCP server, settimeout(), try-except, recv() | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide provides a Python TCP server example demonstrating socket timeouts using `settimeout()` and a `try-except` block to handle unresponsive clients, illustrated with a 'Villagers' toy scenario.

Socket programming: socket timeouts

Application Layer: 2-116

from socket import *
serverPort = 12000
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind(('', serverPort))
serverSocket.listen(1)
counter = 0
while counter < 3:
    connectionSocket, addr = serverSocket.accept()
    connectionSocket.settimeout(10)
    try:
        wolf_location = connectionSocket.recv(1024).decode()
        send_hunter(wolf_location)  # a villager function
        connectionSocket.send('hunter sent')
    except:
        counter += 1
        connectionSocket.close()

Python TCPServer (Villagers)

set a 10-seconds timeout on all future socket operations
catch socket timeout exception
timer starts when recv() is called and will raise timeout exception if there is no message within 10 seconds.

- A shepherd boy tends his master’s sheep.
- If he sees a wolf, he can send a message to the villagers for help using a TCP socket.
- The boy found it fun to connect to the server without sending any messages. But the villagers don’t think so.
- And they decided that if the boy connects to the server and doesn’t send the wolf location within 10 seconds for three times, they will stop listening to him forever and ever.

Toy Example:

---

## Page 117

> **Title:** Application Layer Overview (slides 36-70) | **Type:** example | **Concepts:** SMTP interaction, HELO, MAIL FROM, RCPT TO, DATA, QUIT, SMTP status codes | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide presents a sample SMTP interaction, showcasing the command-response sequence between a client and a server for sending an email, including specific SMTP commands and status codes.

Sample SMTP interaction

Application Layer: 2-117

S: 220 hamburger.edu

C: HELO crepes.fr
S: 250 Hello crepes.fr, pleased to meet you
C: MAIL FROM: <alice@crepes.fr>
S: 250 alice@crepes.fr... Sender ok
C: RCPT TO: <bob@hamburger.edu>
S: 250 bob@hamburger.edu ... Recipient ok
C: DATA
S: 354 Enter mail, end with "." on a line by itself
C: Do you like ketchup?
C: How about pickles?
C: .
S: 250 Message accepted for delivery
C: QUIT
S: 221 hamburger.edu closing connection
---

---

## Page 118

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** diagram_explanation | **Concepts:** CDN content access, DNS resolution, CNAME, KingCDN, netcinema.com | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This diagram explains CDN content access, illustrating how a client requests video content and how DNS resolves the URL to a CDN server for streaming.

CDN content access: a closer look

netcinema.com

KingCDN.com

1. Bob gets URL for video http://netcinema.com/6Y7B23V from netcinema.com web page

2. resolve http://netcinema.com/6Y7B23V via Bob’s local DNS

netcinema’s authoritative DNS

3. netcinema’s DNS returns CNAME for http://KingCDN.com/NetC6y&B23V

4. request video from KINGCDN server, streamed via HTTP

KingCDN authoritative DNS

Bob’s local DNS server

Bob (client) requests video http://netcinema.com/6Y7B23V

• video stored in CDN at http://KingCDN.com/NetC6y&B23V

Application Layer: 2-118
---

---

## Page 119

> **Title:** TCP Socket Programming and Protocols (slides 106-119) | **Type:** diagram_explanation | **Concepts:** Netflix case study, CDN server, Amazon cloud, DASH server, Manifest file, Video streaming | **Chapter:** CH2: Application Layer | **Exam Signal:** No
> **Summary:** This slide presents a Netflix case study, detailing how user requests are routed through Netflix registration servers, Amazon cloud, and CDN servers for video streaming using DASH technology.

Case study: Netflix

Bob manages Netflix account

Netflix registration, accounting servers

Amazon cloud

CDN server


Bob browses Netflix video
Manifest file, requested returned for specific video

DASH server selected, contacted, streaming begins

upload copies of multiple versions of video to CDN servers

CDN server

CDN server



Application Layer: 2-119
