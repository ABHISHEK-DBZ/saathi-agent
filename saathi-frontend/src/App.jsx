import React, { useState, useEffect, useRef } from "react";

// Demo Customers configuration
const DEMO_CUSTOMERS = [
  { id: "DEMO-RAMESH-001", name: "Ramesh Kumar", language: "Hindi", balance: 41000, defaultAmount: 28000 },
  { id: "DEMO-PRIYA-002", name: "Priya Deshpande", language: "Marathi", balance: 89000, defaultAmount: 15500 },
  { id: "DEMO-ARUN-003", name: "Arun Krishnamurthy", language: "Tamil", balance: 125000, defaultAmount: 45000 }
];

export default function App() {
  const [stats, setStats] = useState({
    total_triggered: 0,
    in_conversation: 0,
    converted: 0,
    opted_out: 0
  });
  
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  
  // Controls Panel State
  const [selectedCustomer, setSelectedCustomer] = useState(DEMO_CUSTOMERS[0]);
  const [transactionType, setTransactionType] = useState("salary_credit");
  const [amount, setAmount] = useState(DEMO_CUSTOMERS[0].defaultAmount);
  
  // Real-time progress state
  const [activePipelineEventId, setActivePipelineEventId] = useState(null);
  const [pipelineSteps, setPipelineSteps] = useState({
    supervisor: { status: "idle", time: null },
    life_event_predictor: { status: "idle", time: null },
    product_recommender: { status: "idle", time: null },
    language_adapter: { status: "idle", time: null },
    execution_builder: { status: "idle", time: null }
  });
  
  // Interactive Simulator Input State
  const [chatInput, setChatInput] = useState("");
  const [isSendingChat, setIsSendingChat] = useState(false);
  const [isFiring, setIsFiring] = useState(false);
  const [activeTab, setActiveTab] = useState("Dashboard");
  
  // Security verification state
  const [verificationResult, setVerificationResult] = useState(null);
  const [isVerifying, setIsVerifying] = useState(false);

  // WebSocket reference
  const wsRef = useRef(null);

  // Fetch Stats from backend
  const fetchStats = async () => {
    try {
      const res = await fetch("http://localhost:8000/dashboard/stats");
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.error("Failed to fetch dashboard stats", e);
    }
  };

  // Fetch Event summaries from backend
  const fetchEvents = async () => {
    try {
      const res = await fetch("http://localhost:8000/dashboard/events?limit=20");
      if (res.ok) {
        const data = await res.json();
        setEvents(data);
        if (data.length > 0 && !selectedEvent) {
          fetchEventDetail(data[0].event_id);
        }
      }
    } catch (e) {
      console.error("Failed to fetch event feed", e);
    }
  };

  // Fetch detailed record of a N event
  const fetchEventDetail = async (eventId) => {
    try {
      const res = await fetch(`http://localhost:8000/dashboard/event/${eventId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedEvent(data);
        setVerificationResult(null); // Reset security verification
      }
    } catch (e) {
      console.error(`Failed to fetch event detail for ${eventId}`, e);
    }
  };

  // Setup WebSocket and Initial Data Poll
  useEffect(() => {
    fetchStats();
    fetchEvents();

    const interval = setInterval(fetchStats, 10000);

    const connectWS = () => {
      const ws = new WebSocket("ws://localhost:8000/dashboard/live");
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("WebSocket connected to SAATHI live stream");
      };

      ws.onmessage = (event) => {
        const record = JSON.parse(event.data);
        console.log("WebSocket received event:", record);

        if (record.type === "progress") {
          // Update the real-time agent pipeline steps
          setActivePipelineEventId(record.event_id);
          setPipelineSteps((prev) => {
            const updated = { ...prev };
            // Mark previous nodes as completed if a later node starts
            const nodesOrder = ["supervisor", "life_event_predictor", "product_recommender", "language_adapter", "execution_builder"];
            const currentIdx = nodesOrder.indexOf(record.node);
            
            nodesOrder.forEach((node, idx) => {
              if (idx < currentIdx) {
                if (updated[node].status !== "completed") {
                  updated[node] = { status: "completed", time: updated[node].time || new Date().toLocaleTimeString() };
                }
              }
            });
            
            updated[record.node] = {
              status: record.status || "completed",
              time: new Date().toLocaleTimeString()
            };
            return updated;
          });
          
          // Re-fetch detail for current selected event if progress is for this event
          if (selectedEvent && selectedEvent.event_id === record.event_id) {
            fetchEventDetail(record.event_id);
          }
          return;
        }

        // Standard transaction log update
        setEvents((prev) => {
          const exists = prev.some((e) => e.event_id === record.event_id);
          if (exists) {
            return prev.map((e) => (e.event_id === record.event_id ? { ...e, ...record } : e));
          }
          return [
            {
              event_id: record.event_id,
              trigger_type: record.trigger_type,
              life_event_tag: record.life_event_tag,
              product_id: record.product_id,
              consent_method: record.consent_method,
              created_at: record.consent_at || record.timestamp || new Date().toISOString()
            },
            ...prev
          ];
        });

        // Auto-select newly triggered event
        fetchEventDetail(record.event_id);
        fetchStats();
      };

      ws.onclose = () => {
        console.log("WebSocket disconnected. Retrying in 3s...");
        setTimeout(connectWS, 3000);
      };
    };

    connectWS();

    return () => {
      clearInterval(interval);
      if (wsRef.current) wsRef.current.close();
    };
  }, [selectedEvent]);

  // Sync amount field when customer selection changes
  const handleCustomerChange = (customer) => {
    setSelectedCustomer(customer);
    setAmount(customer.defaultAmount);
  };

  // Trigger Transaction Event Webhook
  const handleFireEvent = async () => {
    setIsFiring(true);
    
    // Reset pipeline tracker for the new event
    setPipelineSteps({
      supervisor: { status: "active", time: new Date().toLocaleTimeString() },
      life_event_predictor: { status: "idle", time: null },
      product_recommender: { status: "idle", time: null },
      language_adapter: { status: "idle", time: null },
      execution_builder: { status: "idle", time: null }
    });

    try {
      const res = await fetch("http://localhost:8000/webhook/transaction", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: selectedCustomer.id,
          transaction_type: transactionType,
          amount: parseFloat(amount),
          account_balance: selectedCustomer.balance,
          timestamp: new Date().toISOString()
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        setActivePipelineEventId(data.event_id);
      }
    } catch (e) {
      console.error("Failed to fire transaction event", e);
    } finally {
      setTimeout(() => {
        setIsFiring(false);
        fetchEvents();
        fetchStats();
      }, 800);
    }
  };

  // Send WhatsApp Reply Simulator
  const handleSendWhatsAppReply = async (messageText) => {
    const textToSend = messageText || chatInput;
    if (!textToSend.trim() || !selectedEvent) return;

    setIsSendingChat(true);
    setChatInput("");

    try {
      // Find customer phone number based on token or context
      const phone = "919876543210"; // standard test phone number
      const res = await fetch("http://localhost:8000/webhook/whatsapp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          object: "whatsapp_business_account",
          entry: [
            {
              id: "123456",
              changes: [
                {
                  value: {
                    messaging_product: "whatsapp",
                    metadata: { display_phone_number: "123456", phone_number_id: "123456" },
                    contacts: [{ profile: { name: selectedCustomer.name }, wa_id: phone }],
                    messages: [
                      {
                        from: phone,
                        id: `wamid.Simulated_${Date.now()}`,
                        timestamp: Math.floor(Date.now() / 1000).toString(),
                        text: { body: textToSend },
                        type: "text"
                      }
                    ]
                  },
                  field: "messages"
                }
              ]
            }
          ]
        })
      });

      if (res.ok) {
        // Wait briefly for processing, then update
        setTimeout(async () => {
          await fetchEventDetail(selectedEvent.event_id);
          await fetchStats();
          setIsSendingChat(false);
        }, 800);
      } else {
        setIsSendingChat(false);
      }
    } catch (e) {
      console.error("Failed to post simulated WhatsApp message", e);
      setIsSendingChat(false);
    }
  };

  // Client-side SHA-256 compliance record verify
  const handleVerifySecurity = async () => {
    if (!selectedEvent) return;
    setIsVerifying(true);
    setVerificationResult(null);

    // Mimic computation latency
    await new Promise((resolve) => setTimeout(resolve, 800));

    try {
      // 1. Separate integrity hash and build raw compliance log representation
      const recordToHash = { ...selectedEvent };
      delete recordToHash.integrity_hash;
      
      // Sort keys to guarantee exact match with python sort_keys=True
      const sortedJsonStr = JSON.stringify(recordToHash, Object.keys(recordToHash).sort());
      
      // 2. Compute SHA-256
      const encoder = new TextEncoder();
      const data = encoder.encode(sortedJsonStr);
      const hashBuffer = await crypto.subtle.digest("SHA-256", data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const computedHash = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");

      if (computedHash === selectedEvent.integrity_hash) {
        setVerificationResult({
          status: "success",
          message: "Cryptographic signature verified. Record is authentic, immutable, and untampered.",
          computedHash
        });
      } else {
        setVerificationResult({
          status: "mismatch",
          computedHash,
          message: "Warning: Computed hash does not match signature. Audit record integrity compromised!"
        });
      }
    } catch (e) {
      setVerificationResult({
        status: "error",
        message: `Verification process failed: ${e.message}`
      });
    } finally {
      setIsVerifying(false);
    }
  };

  const getWhatsAppMessages = () => {
    if (!selectedEvent) return [];
    return selectedEvent.conversation_messages || [];
  };

  return (
    <div className="flex h-screen bg-[#090D1A] text-[#E2E8F0] overflow-hidden font-sans">
      
      {/* 1. Sleek Navigation Sidebar */}
      <div className="w-[240px] bg-[#0E1326] border-r border-[#1F294D] flex flex-col justify-between shrink-0">
        <div>
          {/* Logo Header */}
          <div className="h-[64px] border-b border-[#1F294D] flex items-center px-6 space-x-3 bg-[#090D1A]/50">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#1B3F7A] to-[#E8A020] flex items-center justify-center font-bold text-white shadow-lg">
              S
            </div>
            <div>
              <span className="text-white font-bold tracking-wider text-sm leading-none block">SBI SAATHI</span>
              <span className="text-[10px] text-gray-500 font-mono tracking-widest uppercase">Operations Portal</span>
            </div>
          </div>
          
          {/* Menu Items */}
          <nav className="mt-6 px-3 space-y-1">
            {[
              { id: "Dashboard", label: "Operations Feed", icon: (
                <svg className="w-4 h-4 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
              )},
              { id: "Audit Vault", label: "Security & Auditing", icon: (
                <svg className="w-4 h-4 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
              )}
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center py-2.5 px-4 text-xs font-semibold rounded-lg transition-all duration-150 ${
                  activeTab === tab.id 
                    ? "bg-[#1E294D] text-white shadow-md border-l-4 border-l-[#E8A020]" 
                    : "text-[#B0B8CC] hover:bg-[#1E294D]/35 hover:text-gray-100"
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
        
        {/* Footer */}
        <div className="p-4 border-t border-[#1F294D] bg-[#090D1A]/30 text-[10px] text-gray-500 font-mono space-y-1">
          <div>SBI-WA-2026-SAATHI</div>
          <div className="flex justify-between items-center">
            <span>VERSION: 1.1.0</span>
            <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
          </div>
        </div>
      </div>
      
      {/* 2. Main Portal Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        
        {/* Top Header */}
        <header className="h-[64px] bg-[#0E1326] border-b border-[#1F294D] flex items-center justify-between px-8 shrink-0">
          <div className="flex items-center space-x-3">
            <span className="text-xs bg-[#E8A020]/10 text-[#E8A020] border border-[#E8A020]/20 font-bold px-2 py-0.5 rounded uppercase tracking-wider">
              System Live
            </span>
            <h1 className="text-white text-xs font-semibold uppercase tracking-wider">
              Vernacular Inclusion Sandbox & Audit Center
            </h1>
          </div>
          <div className="flex items-center space-x-4">
            <div className="text-[11px] font-mono text-gray-400">
              Session Time: {new Date().toLocaleDateString()}
            </div>
            <div className="flex items-center space-x-2 bg-[#090D1A] px-3 py-1 rounded border border-[#1F294D]">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="text-[10px] text-emerald-400 font-mono uppercase tracking-wider font-bold">WS Live</span>
            </div>
          </div>
        </header>
        
        {/* Workspace Panels */}
        <main className="flex-1 p-8 overflow-y-auto space-y-8 bg-[#090D1A]">
          
          {activeTab === "Dashboard" ? (
            <>
              {/* KPI Stat Cards Grid */}
              <div className="grid grid-cols-4 gap-6">
                {[
                  { label: "Total Alerts Triggered", val: stats.total_triggered, color: "text-white" },
                  { label: "Active Conversations", val: stats.in_conversation, color: "text-sky-400" },
                  { label: "Consents Obtained", val: stats.converted, color: "text-amber-400", border: "border-l-4 border-l-[#E8A020]" },
                  { label: "Out-Out Status", val: stats.opted_out, color: "text-red-500" }
                ].map((stat, idx) => (
                  <div key={idx} className={`bg-[#0E1326] border border-[#1F294D] rounded-xl p-5 shadow-lg ${stat.border || ""}`}>
                    <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                      {stat.label}
                    </div>
                    <div className={`font-mono text-3xl font-bold leading-none tracking-tight mt-2.5 ${stat.color}`}>
                      {stat.val}
                    </div>
                  </div>
                ))}
              </div>

              {/* Main Core Layout: Left Event feed / Right details & preview */}
              <div className="grid grid-cols-12 gap-8 items-start">
                
                {/* 1. Left Column (Live Event feed) */}
                <div className="col-span-7 bg-[#0E1326] border border-[#1F294D] rounded-xl overflow-hidden shadow-lg">
                  <div className="px-5 py-4 border-b border-[#1F294D] bg-[#0E1326]/50 flex justify-between items-center">
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">Live Transaction Alerts Feed</h3>
                    <span className="text-[10px] text-gray-500 font-mono">Real-Time WebSocket Stream</span>
                  </div>
                  
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-[#1F294D] bg-[#0A0E1C] text-[10px] text-gray-500 uppercase font-bold tracking-wider">
                          <th className="px-5 py-3">Time</th>
                          <th className="px-4 py-3">Transaction Event</th>
                          <th className="px-4 py-3">Customer Token</th>
                          <th className="px-4 py-3">Target Product</th>
                          <th className="px-5 py-3 text-right">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1F294D] font-mono text-[11px]">
                        {events.length === 0 ? (
                          <tr>
                            <td colSpan="5" className="px-5 py-12 text-center text-gray-500 italic">
                              No transaction logs. Use simulation controls below to trigger alerts.
                            </td>
                          </tr>
                        ) : (
                          events.map((evt) => {
                            const isSelected = selectedEvent && selectedEvent.event_id === evt.event_id;
                            let statusText = "Active";
                            let statusColor = "bg-amber-500/10 text-amber-400 border-amber-500/30";
                            
                            if (evt.consent_method) {
                              statusText = "Converted";
                              statusColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
                            } else if (evt.stage === "opted_out") {
                              statusText = "Opted Out";
                              statusColor = "bg-red-500/10 text-red-400 border-red-500/30";
                            }

                            return (
                              <tr
                                key={evt.event_id}
                                onClick={() => fetchEventDetail(evt.event_id)}
                                className={`cursor-pointer transition-all duration-100 ${
                                  isSelected 
                                    ? "bg-[#1E294D]/30 border-l-4 border-l-[#E8A020]" 
                                    : "hover:bg-[#1E294D]/10"
                                }`}
                              >
                                <td className="px-5 py-3.5 text-gray-400">
                                  {evt.created_at ? new Date(evt.created_at).toLocaleTimeString() : "--:--"}
                                </td>
                                <td className="px-4 py-3.5 text-white font-semibold">
                                  {evt.trigger_type}
                                </td>
                                <td className="px-4 py-3.5 text-gray-500">
                                  {evt.customer_token ? `CUST-${evt.customer_token.slice(0, 8)}` : "Guest"}
                                </td>
                                <td className="px-4 py-3.5 text-emerald-400 font-semibold">
                                  {evt.product_id ? evt.product_id.replace("SBI_", "") : "Pending"}
                                </td>
                                <td className="px-5 py-3.5 text-right">
                                  <span className={`text-[9px] font-bold uppercase px-2 py-0.5 border rounded ${statusColor}`}>
                                    {statusText}
                                  </span>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* 2. Right Column (Agent logs & WhatsApp Preview) */}
                <div className="col-span-5 space-y-6">
                  
                  {/* Pipeline Tracing View */}
                  <div className="bg-[#0E1326] border border-[#1F294D] rounded-xl p-5 shadow-lg space-y-4">
                    <div className="flex justify-between items-center border-b border-[#1F294D] pb-3">
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider">Live Agent Exec Timeline</h3>
                      <span className="text-[9px] font-mono text-gray-500">Node Streaming State</span>
                    </div>

                    <div className="space-y-4">
                      {Object.keys(pipelineSteps).map((step, idx) => {
                        const info = pipelineSteps[step];
                        let statusColor = "bg-gray-800 text-gray-500 border-gray-700";
                        let ringColor = "";
                        
                        if (info.status === "active") {
                          statusColor = "bg-amber-500/10 text-amber-400 border-amber-400/50";
                          ringColor = "ring-2 ring-amber-400 animate-pulse";
                        } else if (info.status === "completed") {
                          statusColor = "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
                        }

                        return (
                          <div key={step} className="flex items-center space-x-3.5 text-xs">
                            <div className={`w-6 h-6 rounded-full border flex items-center justify-center font-bold font-mono ${statusColor} ${ringColor}`}>
                              {idx + 1}
                            </div>
                            <div className="flex-1">
                              <div className="font-semibold text-gray-200 capitalize">
                                {step.replace(/_/g, " ")}
                              </div>
                              <div className="text-[9px] text-gray-500 font-mono">
                                {info.status === "active" ? "Analyzing Context..." : info.status === "completed" ? "Success ✓" : "Awaiting Trigger"}
                              </div>
                            </div>
                            <div className="text-[10px] font-mono text-gray-500">
                              {info.time || "--:--:--"}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* WhatsApp Simulator Frame */}
                  <div className="bg-[#0E1326] border border-[#1F294D] rounded-xl overflow-hidden shadow-lg flex flex-col">
                    
                    {/* Simulator Header */}
                    <div className="bg-[#075E54] px-4 py-3 flex items-center justify-between shrink-0">
                      <div className="flex items-center space-x-3">
                        <div className="w-9 h-9 rounded-full bg-[#128C7E] flex items-center justify-center font-bold text-white text-xs shadow">
                          SBI
                        </div>
                        <div>
                          <div className="text-xs font-bold text-white leading-tight">SBI SAATHI Assistant</div>
                          <div className="text-[9px] text-[#25D366] leading-none font-semibold">Online Chat Sandbox</div>
                        </div>
                      </div>
                      <div className="text-[9px] font-mono bg-black/20 text-[#25D366] px-1.5 py-0.5 rounded">
                        PROACTIVE
                      </div>
                    </div>
                    
                    {/* Message Log Container */}
                    <div 
                      className="p-4 space-y-3 h-[280px] overflow-y-auto flex flex-col"
                      style={{ backgroundColor: "#0B0E14", backgroundImage: "radial-gradient(#1e293b 1.2px, transparent 0)", backgroundSize: "18px 18px" }}
                    >
                      {selectedEvent ? (
                        <>
                          {getWhatsAppMessages().map((msg, i) => {
                            const isOutbound = msg.direction === "outbound";
                            return (
                              <div key={i} className={`flex ${isOutbound ? "justify-end" : "justify-start"} w-full`}>
                                <div 
                                  className={`max-w-[85%] rounded-lg p-2.5 text-xs shadow-md whitespace-pre-line relative ${
                                    isOutbound 
                                      ? "bg-[#056162] text-white border border-[#067273]" 
                                      : "bg-[#262D31] text-gray-200 border border-[#2e373b]"
                                  }`}
                                >
                                  {msg.content}
                                  <span className="block text-right text-[8px] text-gray-400 mt-1 font-mono">
                                    {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : ""}
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                        </>
                      ) : (
                        <div className="m-auto text-center text-gray-500 font-mono text-xs">
                          Awaiting webhook transaction alert...
                        </div>
                      )}
                    </div>
                    
                    {/* Interactive Input Form */}
                    {selectedEvent && (
                      <div className="p-3 border-t border-[#1F294D] bg-[#0E1326] space-y-3 shrink-0">
                        {/* Quick Reply Chips */}
                        <div className="flex flex-wrap gap-1.5">
                          {selectedEvent.consent_obtained ? (
                            <span className="text-[10px] font-mono text-emerald-400 font-semibold px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 rounded">
                              ✓ Consent Fully Verification Complete
                            </span>
                          ) : (
                            <>
                              <button 
                                onClick={() => handleSendWhatsAppReply("1")}
                                className="text-[9px] font-bold bg-[#1E294D] hover:bg-[#1E294D]/70 text-gray-200 px-2 py-1 border border-[#2b3967] rounded transition-colors"
                              >
                                Chip: "1" (Haan/Proceed)
                              </button>
                              <button 
                                onClick={() => handleSendWhatsAppReply("123456")}
                                className="text-[9px] font-bold bg-[#1E294D] hover:bg-[#1E294D]/70 text-gray-200 px-2 py-1 border border-[#2b3967] rounded transition-colors"
                              >
                                Chip: "123456" (Enter OTP)
                              </button>
                              <button 
                                onClick={() => handleSendWhatsAppReply("3")}
                                className="text-[9px] font-bold bg-red-950/20 hover:bg-red-950/40 text-red-400 px-2 py-1 border border-red-900/30 rounded transition-colors"
                              >
                                Chip: "3" (Opt Out)
                              </button>
                            </>
                          )}
                        </div>

                        {/* Input Controls */}
                        {!selectedEvent.consent_obtained && (
                          <div className="flex items-center space-x-2">
                            <input
                              type="text"
                              placeholder="Type message reply (e.g. 1, 123456)..."
                              value={chatInput}
                              onChange={(e) => setChatInput(e.target.value)}
                              onKeyDown={(e) => e.key === "Enter" && handleSendWhatsAppReply()}
                              className="flex-1 bg-[#1A1F38] border border-[#1F294D] rounded px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#E8A020] font-semibold"
                            />
                            <button
                              onClick={() => handleSendWhatsAppReply()}
                              disabled={isSendingChat || !chatInput.trim()}
                              className="bg-[#056162] hover:bg-[#077273] text-white text-xs font-bold px-3 py-1.5 rounded transition-colors disabled:opacity-40"
                            >
                              {isSendingChat ? "..." : "Send"}
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                  </div>
                </div>

              </div>

              {/* Demo Controls Dashboard Pane */}
              <div className="bg-[#0E1326] border border-[#1F294D] rounded-xl p-6 shadow-lg space-y-4">
                <div className="border-b border-[#1F294D] pb-3">
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">Demo Event Simulator Operations Panel</h3>
                </div>

                <div className="grid grid-cols-12 gap-6 items-end">
                  {/* Select Customer Profile */}
                  <div className="col-span-4 flex flex-col space-y-2">
                    <label className="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Select Sandbox Profile</label>
                    <select
                      value={selectedCustomer.id}
                      onChange={(e) => handleCustomerChange(DEMO_CUSTOMERS.find(c => c.id === e.target.value))}
                      className="bg-[#1A1F38] border border-[#1F294D] text-xs text-white px-3 py-2 rounded-lg focus:outline-none focus:border-[#E8A020] font-semibold"
                    >
                      {DEMO_CUSTOMERS.map((cust) => (
                        <option key={cust.id} value={cust.id}>
                          {cust.name} ({cust.language})
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Transaction Amount */}
                  <div className="col-span-3 flex flex-col space-y-2">
                    <label className="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Transaction Amount (INR)</label>
                    <input
                      type="number"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      className="bg-[#1A1F38] border border-[#1F294D] text-xs text-white px-3 py-2 rounded-lg focus:outline-none focus:border-[#E8A020] font-semibold font-mono"
                    />
                  </div>

                  {/* Trigger Signal Type Selection */}
                  <div className="col-span-3 flex flex-col space-y-2">
                    <label className="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Event Signal Type</label>
                    <div className="flex space-x-4 py-2">
                      {[
                        { id: "salary_credit", label: "Salary" },
                        { id: "emi_cleared", label: "EMI Stopped" },
                        { id: "high_travel_spend", label: "Travel Gap" }
                      ].map((t) => (
                        <label key={t.id} className="flex items-center space-x-2 text-xs font-semibold cursor-pointer">
                          <input
                            type="radio"
                            name="transaction_type"
                            value={t.id}
                            checked={transactionType === t.id}
                            onChange={() => setTransactionType(t.id)}
                            className="text-[#E8A020] focus:ring-0 bg-[#1A1F38] border-[#1F294D]"
                          />
                          <span className="text-gray-300">{t.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Trigger Action Button */}
                  <div className="col-span-2">
                    <button
                      onClick={handleFireEvent}
                      disabled={isFiring}
                      className="w-full bg-[#1B3F7A] hover:bg-[#2557a6] text-white text-xs font-bold py-2.5 rounded-lg transition-colors shadow-md disabled:opacity-50"
                    >
                      {isFiring ? "Filing Signal..." : "▶ Fire Webhook"}
                    </button>
                  </div>
                </div>
              </div>
            </>
          ) : (
            /* Tab: Security & Compliance Audit Vault */
            <div className="bg-[#0E1326] border border-[#1F294D] rounded-xl p-6 shadow-lg space-y-6">
              <div className="border-b border-[#1F294D] pb-3 flex justify-between items-center">
                <div>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">RBI Compliance Audit & Vault</h3>
                  <p className="text-[10px] text-gray-500 mt-1">Verify data integrity signature for regulatory monitoring</p>
                </div>
                <span className="text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded">
                  SHA-256 Compliant
                </span>
              </div>

              {selectedEvent ? (
                <div className="space-y-6">
                  {/* Detailed Log Summary Info */}
                  <div className="grid grid-cols-2 gap-6 text-xs font-mono">
                    <div className="space-y-3">
                      <div className="flex"><span className="w-[140px] text-gray-500 font-bold uppercase">Event ID:</span><span className="text-white">{selectedEvent.event_id}</span></div>
                      <div className="flex"><span className="w-[140px] text-gray-500 font-bold uppercase">Customer Token:</span><span className="text-white break-all">{selectedEvent.customer_token}</span></div>
                      <div className="flex"><span className="w-[140px] text-gray-500 font-bold uppercase">Trigger Type:</span><span className="text-white">{selectedEvent.trigger_type}</span></div>
                      <div className="flex">
                        <span className="w-[140px] text-gray-500 font-bold uppercase">Maturity Status:</span>
                        <span className={selectedEvent.consent_obtained ? "text-emerald-400 font-bold" : "text-amber-400"}>
                          {selectedEvent.consent_obtained ? "✓ CONSENT SIGNED" : "✗ PENDING"}
                        </span>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <div className="flex"><span className="w-[140px] text-gray-500 font-bold uppercase">Recommended:</span><span className="text-emerald-400 font-bold">{selectedEvent.product_id}</span></div>
                      <div className="flex"><span className="w-[140px] text-gray-500 font-bold uppercase">Consent Method:</span><span className="text-white">{selectedEvent.consent_method || "N/A"}</span></div>
                      <div className="flex"><span className="w-[140px] text-gray-500 font-bold uppercase">Created At:</span><span className="text-white">{selectedEvent.timestamp}</span></div>
                      <div className="flex"><span className="w-[140px] text-gray-500 font-bold uppercase">DB Signature Hash:</span><span className="text-gray-400 break-all select-all font-bold">{selectedEvent.integrity_hash}</span></div>
                    </div>
                  </div>

                  {/* Recommendation Rationale display */}
                  <div className="bg-[#1A1F38] border border-[#1F294D] p-4 rounded-lg">
                    <div className="text-[10px] font-bold text-[#E8A020] uppercase tracking-wider mb-2">Auditable Rationale RAG Logic</div>
                    <div className="text-xs text-gray-300 leading-relaxed font-mono">{selectedEvent.rationale}</div>
                  </div>

                  {/* Security Verification Panel */}
                  <div className="border-t border-[#1F294D] pt-5 space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-semibold text-gray-300">Run security audit check:</span>
                      <button
                        onClick={handleVerifySecurity}
                        disabled={isVerifying}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold px-4 py-2 rounded-lg transition-colors flex items-center space-x-2"
                      >
                        {isVerifying ? "Verifying Hash..." : "Verify Record Integrity"}
                      </button>
                    </div>

                    {verificationResult && (
                      <div className={`p-4 rounded-lg flex items-start space-x-3 text-xs ${
                        verificationResult.status === "success" 
                          ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400" 
                          : "bg-red-500/10 border border-red-500/20 text-red-400"
                      }`}>
                        <div className="text-lg">
                          {verificationResult.status === "success" ? "🛡️" : "⚠️"}
                        </div>
                        <div className="space-y-1">
                          <div className="font-bold">{verificationResult.message}</div>
                          <div className="text-[10px] font-mono break-all text-gray-500 mt-1">
                            Computed SHA-256 Hash: {verificationResult.computedHash}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center text-gray-500 font-mono text-xs">
                  No active transaction selected. Go to Operations Feed and select a row to inspect its security signature.
                </div>
              )}
            </div>
          )}

        </main>
      </div>

    </div>
  );
}
