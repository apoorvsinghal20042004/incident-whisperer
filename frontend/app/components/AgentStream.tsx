"use client"

import { useEffect, useState } from "react"

interface AgentEvent{
    agent: string
    event_type: string
    data: Record<string, unknown>
}

interface AgentStreamProps{
    incidentId: string
}

export default function AgentStream({incidentId}: AgentStreamProps){
    // state that holds an arr of agent events. starts empty. every new
    // agent gets appended.
    const [events, setEvents] = useState<AgentEvent[]>([])
    // useState(false) twice- one for connection status, one for pipeline completion
    const [connected, setConnected] = useState(false)
    const [complete, setComplete] = useState(false)

    // useEffect(() => {...}, [incidentId])
    // runs when component first appears AND whenever incidentId changes. the 
    // [incidentId] dependancy array means: "rerun this effect if incidentId change"

    useEffect(() => {
        const url = `http://localhost:8000/stream/incidents/${incidentId}`
        // browser's built in SSE client
        // opens a persistent connection to our FastAPI streaming endpoint
        const eventSource = new EventSource(url)

        eventSource.onopen = () => {
            setConnected(true)
        }
        eventSource.onmessage = (e) =>{
            // callback that fires every time an event arrives. We parse JSON, ignore
            // connected event, and append everything else to state
            const event: AgentEvent = JSON.parse(e.data)
            if(event.event_type === "connected") return
            // prev is current state. we spread it(...prev) into a new array and append the new
            // event. never mutate state directly
            setEvents((prev) => [...prev, event])
            if(event.event_type === "pipeline_complete"){
                setComplete(true)
                eventSource.close()
            }
        }
        eventSource.onerror = () => {
            eventSource.close()
        }
        return () => {
            eventSource.close()
        }
    }, [incidentId])
    return (
        <div className="space-y-3">
          <div className="flex items-center gap-2 mb-4">
            <div className={`w-2 h-2 rounded-full ${complete ? "bg-green-500" : connected ? "bg-blue-500 animate-pulse" : "bg-gray-500"}`} />
            <span className="text-sm text-gray-400">
              {complete ? "Analysis complete" : connected ? "Agents running..." : "Connecting..."}
            </span>
          </div>
    
          {events.map((event, index) => (
            <div
              key={index}
              className="bg-gray-900 border border-gray-800 rounded-lg p-4"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono text-blue-400">
                  {event.agent}
                </span>
                <span className="text-xs text-gray-500">
                  {event.event_type}
                </span>
              </div>
              <p className="text-sm text-gray-300">
                {typeof event.data === "object" && "message" in event.data
                  ? String(event.data.message)
                  : JSON.stringify(event.data)}
              </p>
            </div>
          ))}
    
          {events.length === 0 && connected && (
            <p className="text-gray-500 text-sm italic">
              Waiting for agent events...
            </p>
          )}
        </div>
      )
    }