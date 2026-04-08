#include <iostream>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <limits>
#include <time.h>

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/tap-bridge-module.h"
//#include "ns3/mpi-interface.h"

#include "ns3/netanim-module.h"

#include "ns3/internet-module.h"
#include "ns3/ipv4-global-routing-helper.h"
#include "ns3/applications-module.h"

#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/tap-bridge-module.h"

using namespace ns3;

NS_LOG_COMPONENT_DEFINE ("TapWifiVirtualMachineExample");


class TargetServer : public Application
{
public:

  TargetServer();
  virtual ~TargetServer();

  Ptr<Socket> GetListeningSocket(void) const;

  void Setup(uint16_t Port, int numnodes, int log, char *outputDir);

protected:
  virtual void DoDispose(void);

private:
  virtual void StartApplication(void);
  virtual void StopApplication(void);

  void OutData(void);

  void HandleAccept(Ptr<Socket> socket, const Address& from);
  void HandleRead(Ptr<Socket> socket);
  void HandlePeerClose(Ptr<Socket> socket);
  void HandlePeerError(Ptr<Socket> socket);
  void Initiate(void);

  Ptr<Socket>       m_socket;

  Address           tx_peer;
  TypeId            tid;
  Address           local;

  int               file_log;
  double            totalBytes;
  double            startStastics;
  double            endStastics;
  std::ofstream     myAppData;
  char              thrName[500];
  Time              collect;
  EventId           m_collectEvent;
};
TargetServer::TargetServer()
  : m_socket(nullptr),
    local()
{
  file_log = 0;
}

TargetServer::~TargetServer()
{
  m_socket = nullptr;

  if (myAppData.is_open())
  {
    myAppData.close();
  }
}


Ptr<Socket>
TargetServer::GetListeningSocket(void) const
{
  return m_socket;
}

void
TargetServer::DoDispose(void)
{
  <<"Simulation Time: "
  <<(Simulator::Now ().As (Time::S))
  <<" NS3 finished running"

  Simulator::Cancel (m_collectEvent);
  m_socket = nullptr;

  // chain up
  Application::DoDispose();
}

void
TargetServer::StartApplication() // Called at time specified by Start
{
  if (!m_socket)
  {
    m_socket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
    if (!local.IsInvalid())
    {
      if (m_socket->Bind (local) == -1)
      {
        NS_FATAL_ERROR ("Failed to bind socket");
      }
    }

    m_socket->Listen();
  }

  m_socket->SetRecvCallback(MakeCallback(&TargetServer::HandleRead, this));
  m_socket->SetAcceptCallback(
      MakeNullCallback<bool, Ptr<Socket>, const Address &>(),
      MakeCallback(&TargetServer::HandleAccept, this));
  m_socket->SetCloseCallbacks(
      MakeCallback(&TargetServer::HandlePeerClose, this),
      MakeCallback(&TargetServer::HandlePeerError, this));
}

void
TargetServer::StopApplication() // Called at time specified by Stop
{
  Simulator::Cancel (m_collectEvent);
  if (m_socket)
  {
    m_socket->Close();
    m_socket->SetRecvCallback(MakeNullCallback<void, Ptr<Socket> >());
  }
}

void
TargetServer::HandleRead(Ptr<Socket> socket)
{
  Ptr<Packet> packet;
  Address from;
  Address localAddress;
  while ((packet = socket->RecvFrom(from)))
  {
    socket->GetSockName (localAddress);

    if (packet->GetSize() == 0)
    { //EOF
      break;
    }

    //start our statistics
    if (Simulator::Now() > (collect))
    {
      totalBytes += packet->GetSize ();
      endStastics = Simulator::Now().ToDouble(ns3::Time::MS);
    }

    if (InetSocketAddress::IsMatchingType(from))
    {
      NS_LOG_DEBUG("At time " << Simulator::Now ().As (Time::S)
                  << " server received " << packet->GetSize()
                  << " bytes from " << InetSocketAddress::ConvertFrom(from).GetIpv4()
                  << " port " << InetSocketAddress::ConvertFrom(from).GetPort());
    }
  }
}

void
TargetServer::HandlePeerClose(Ptr<Socket> socket)
{
  NS_LOG_FUNCTION(this << socket);
}

void
TargetServer::HandlePeerError(Ptr<Socket> socket)
{
  NS_LOG_FUNCTION(this << socket);
}

void
TargetServer::HandleAccept(Ptr<Socket> s, const Address& from)
{
  s->SetRecvCallback(MakeCallback(&TargetServer::HandleRead, this));
}

void
TargetServer::Setup(uint16_t m_port, int numnodes, int log, char * outputDir)
{
  file_log = log;

  local = InetSocketAddress(Ipv4Address::GetAny(), m_port);
  collect = Seconds(10);

  startStastics =  collect.ToDouble(ns3::Time::MS);
  totalBytes = 0.0;
  endStastics = 0.0;

  if (file_log == 2)
  {
    sprintf(thrName, "%s/throughput_wifi_%d.txt", outputDir,numnodes);

    //if file exists, then remove it
    std::ifstream fstr(thrName);
    if (fstr.good())
    {
      std::remove(thrName);
    }

    m_collectEvent = Simulator::Schedule (Seconds(1.0), &TargetServer::OutData, this);
  }
}

void
TargetServer::OutData(void)
{
  if (Simulator::Now() > (collect))
  {
    double duration = (endStastics - startStastics) / 1000.0;

    myAppData.open(thrName, std::ios::app);

    if (!myAppData.is_open())
    {
      NS_FATAL_ERROR ("Unable to create a file to store the output");
    }

    myAppData << std::setprecision(2) << Simulator::Now().ToDouble(ns3::Time::S)
    << "\t" << std::fixed<< std::setprecision(9) << ((totalBytes == 0.0) ? 0.0 : ((totalBytes * 8.0 ) / duration)) << "\n";
    myAppData.close();
  }

  totalBytes = 0.0;
  startStastics = Simulator::Now().ToDouble(ns3::Time::MS);

  m_collectEvent = Simulator::Schedule (Seconds(1.0), &TargetServer::OutData, this);
}

void
Churn(bool isChurn[], NetDeviceContainer *devs, int churn_lev)
{
  double q_h, e_h, l_h,L_h;
  double phi_1 = 0.16, phi_2 = 0.08, phi_3 = 0.04;
  double churn_threshold = 0.04;
  Time dyna_churn_dur = Seconds(20); 
  int NumNodes = (*devs).GetN();

  for (int i = 2; i < NumNodes; i++) // 1 is Attacker (no churn for Attacker)
  {
    Ptr<UniformRandomVariable> x = CreateObject<UniformRandomVariable>();

    RngSeedManager::SetSeed(time(NULL));  // Changes seed
    RngSeedManager::SetRun(time(NULL));   // Changes run number

    q_h = x->GetValue(0, 1);
    e_h = x->GetValue(0, 1);

    L_h = (1 - q_h) * (1 - e_h);

    if (L_h <= 0.4)
      l_h = phi_1 * L_h;
    else if (L_h > 0.4 && L_h <= 0.7)
      l_h = phi_2 * L_h;
    else
      l_h = phi_3 * L_h;

    double value = (int)(l_h * 100 + .5);
    double round_val =  (double)value / 100;

    NS_LOG_UNCOND("Time:"<< Simulator::Now().ToDouble(ns3::Time::S)
      <<" Node:"<<(i+1)<<" q(h):" << (q_h)<<" e(h):" << (e_h)
      <<" L(h):" << (L_h)<<" l(h):" << (l_h)<<" p:"<<round_val<<"\n");

    Ptr<WifiNetDevice> curr_wifi_net = DynamicCast<WifiNetDevice>((*devs).Get(i));
    Ptr<WifiPhy> curr_wifi_py = DynamicCast<WifiPhy>(curr_wifi_net->GetPhy());
    Ptr<WifiPhyStateHelper> state_phy = curr_wifi_py->GetState();

    if (round_val >= churn_threshold)
    {
      isChurn[i] = true;
      NS_LOG_UNCOND("\nNode = "<<(i+1)<<" churn off before: "<<!(state_phy->IsStateOff()));
      if (!(state_phy->IsStateOff()))
      {
        state_phy->SwitchToOff();
      }
      NS_LOG_UNCOND("Node = "<<(i+1)<<" churn off after: "<<!(state_phy->IsStateOff()));
    }
    else if (isChurn[i])
    {
      isChurn[i] = false;
      NS_LOG_UNCOND("\nNode = "<<(i+1)<<" churn on before: "<<!(state_phy->IsStateOff()));
      if (state_phy->IsStateOff())
      {
        state_phy->SwitchFromOff();
      }
      NS_LOG_UNCOND("Node = "<<(i+1)<<" churn on after: "<<!(state_phy->IsStateOff()));
    }
  }

  int churn_nodes = 0;
  for(int i = 2; i < NumNodes; i++)
  {
      if (isChurn[i])
      {
        churn_nodes++;
      }
  }
  NS_LOG_INFO("churn nodes #:"<<churn_nodes<<"\n");

  if (churn_lev == 2)
    Simulator::Schedule (dyna_churn_dur, &Churn, isChurn, devs, churn_lev);
}


int
main (int argc, char *argv[])
{
  bool AnimationOn = false;
  int NumNodes = 10;
  double TotalTime = 600.0;

  double distance = 5;

  int churn = 0; // 0 => no churn, 1 => static, 2 => dynamic
  int log = 0;   // 0 => disabled, 1 => log stats, 2 => log all

  std::string TapBaseName = "emu";
  std::string mode = "UseLocal";

  LogComponentEnable ("TapWifiVirtualMachineExample", LOG_LEVEL_ALL); //LOG_LEVEL_DEBUG //LOG_LEVEL_INFO

  CommandLine cmd;
  cmd.AddValue ("NumNodes", "Number of nodes/devices", NumNodes);
  cmd.AddValue ("TotalTime", "Total simulation time", TotalTime);
  cmd.AddValue ("TapBaseName", "Base name for tap interfaces", TapBaseName);
  cmd.AddValue ("DiskDistance", "Disk distance", distance);
  cmd.AddValue ("AnimationOn", "Enable animation", AnimationOn);
  cmd.AddValue ("Churn", "Churn level", churn);
  cmd.AddValue ("FileLog", "Enable log data to file", log);

  cmd.Parse (argc,argv);

  GlobalValue::Bind("SimulatorImplementationType", StringValue ("ns3::RealtimeSimulatorImpl"));
  GlobalValue::Bind("ChecksumEnabled", BooleanValue (true));

  NS_LOG_UNCOND ("Running simulation in wifi adhoc mode");

  NS_LOG_UNCOND ("Creating nodes");
  NodeContainer nodes;
  nodes.Create (NumNodes);

  NS_LOG_UNCOND ("Creating wifi");
  WifiHelper wifi;
  wifi.SetStandard(WIFI_STANDARD_80211a);
  wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                               "DataMode",
                               StringValue("OfdmRate54Mbps"));

  NS_LOG_UNCOND ("Creating ad hoc wifi mac");
  WifiMacHelper wifiMac;
  wifiMac.SetType ("ns3::AdhocWifiMac");

  NS_LOG_UNCOND ("Configuring physical layer");
  YansWifiChannelHelper wifiChannel = YansWifiChannelHelper::Default ();
  YansWifiPhyHelper wifiPhy;
  wifiPhy.SetChannel (wifiChannel.Create ());

  NetDeviceContainer devices = wifi.Install (wifiPhy, wifiMac, nodes);

  InternetStackHelper internetRight;
  internetRight.Install (nodes);

  Ipv4AddressHelper ipv4Right;
  ipv4Right.SetBase ("10.0.0.0", "255.0.0.0");
  Ipv4InterfaceContainer interfacesRight = ipv4Right.Assign (devices);

  NS_LOG_UNCOND ("Configuring mobility");
  MobilityHelper mobility;

  mobility.SetPositionAllocator("ns3::UniformDiscPositionAllocator",
                                       "X", ns3::DoubleValue(0.0),
                                       "Y", ns3::DoubleValue(0.0),
                                       "rho", ns3::DoubleValue(distance)); // radius in meters
  mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  mobility.Install(nodes); // Install to the other nodes  

  // the following is to obtain desktop dir to store output
  char outputDir[200];
  FILE *f = popen("echo ~/Desktop", "r");
  while (fgets(outputDir, 100, f) != NULL) {}
  pclose(f);

  size_t ln = strlen(outputDir) - 1;
  if (*outputDir && outputDir[ln] == '\n')
    outputDir[ln] = '\0';

  uint16_t port = 9;  // well-known echo port number

  NS_LOG_INFO("Creating Taregt Server Application");
  Ptr<TargetServer> tServer = CreateObject<TargetServer>();
  nodes.Get (0)->AddApplication(tServer);
  tServer->Setup(port, (NumNodes - 1), log, outputDir);
  tServer->SetStartTime(Seconds(0.));
  tServer->SetStopTime(Seconds(TotalTime));

  Ptr<NetDevice> PtrNetDevice;
  {
    Ptr <Node> PtrNode = nodes.Get (0);
    PtrNetDevice = PtrNode->GetDevice(0);
    Ptr<Ipv4> ipv4 = PtrNode->GetObject<Ipv4> ();
    Ipv4InterfaceAddress iaddr = ipv4->GetAddress (1,0);
    Ipv4Address ipAddr = iaddr.GetLocal ();

    std::cout<<"\n****************************************"
    <<"\nTarget Server IPv4: "<<ipAddr
    <<"\nTarget Server MAC:"<<(PtrNetDevice->GetAddress())
    <<"\n****************************************\n\n";
  }

  NS_LOG_UNCOND ("Creating tap bridges");
  TapBridgeHelper tapBridge;
  tapBridge.SetAttribute ("Mode", StringValue(mode));

  for (int i = 1; i < NumNodes; i++)
  {
    std::stringstream tapName;
    tapName << "tap-" << TapBaseName << (i+1) ;
    NS_LOG_UNCOND ("Tap bridge = " + tapName.str ());

    tapBridge.SetAttribute ("DeviceName", StringValue (tapName.str ()));
    tapBridge.Install (nodes.Get (i), devices.Get (i));
  }

  // churn
  if (churn != 0)
  {
    bool isChurn[NumNodes + 1];
    for(int i = 0; i <= NumNodes; i++)
    {
        isChurn[i] = false;
    }

    Churn(isChurn, &devices, churn);
  }

  Ipv4GlobalRoutingHelper::PopulateRoutingTables ();

  // dedicated pcap output
  std::string outputf = std::string (outputDir) + "/captured_packets_wifi_"+std::to_string(NumNodes-1);

  if (log == 1)
  {
    wifiPhy.EnablePcap(outputf, PtrNetDevice, true);
  }

  // iterate our nodes and print their position.
  for (NodeContainer::Iterator j = nodes.Begin(); j != nodes.End(); ++j)
  {
      Ptr<Node> object = *j;
      uint32_t id = object->GetId();
      Ptr<MobilityModel> position = object->GetObject<MobilityModel>();
      NS_ASSERT(position);
      Vector pos = position->GetPosition();
      NS_LOG_UNCOND("node="<<id<<" x=" << pos.x << ", y=" << pos.y << ", z=" << pos.z);
  }

  NS_LOG_UNCOND ("\nRunning simulation in wifi mode");
  Simulator::Stop (Seconds (TotalTime));
  Simulator::Run ();
  Simulator::Destroy ();

  return 0;
