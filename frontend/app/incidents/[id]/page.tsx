import AgentStream from "@/app/components/AgentStream"

interface Incident {
    id: string
    affected_service: string
    severity: string
    status: string
    root_cause: string | null
    confidence_score: number | null
    remediation_steps: string[] | null
    created_at: string
    updated_at: string
}

async function getIncident(id: string): Promise<Incident | null> {
    try{
        const response = await fetch(`http://localhost:8000/incidents/${id}`,{
            cache: "no-store",
        })
        if(!response.ok) return null
        return response.json()
    } catch {
        return null
    }
}

export default async function IncidentDetailPage({
    params,
}:{
    // In Next.js 15, route params are now a Promise — you must await them. 
    // The [id] folder name becomes a parameter automatically.
    params: Promise<{ id: string}>
}) {
    const { id } = await params
    const incident = await getIncident(id)
    if(!incident){
        return (
            <main className="max-w-5xl mx-auto px-6 py-10">
              <p className="text-gray-400">Incident not found.</p>
            </main>
        )
    }
    return (
        <main className="max-w-5xl mx-auto px-6 py-10">
          <div className="mb-6">
            <a href="/incidents" className="text-sm text-gray-500 hover:text-gray-300">
              Back to incidents
            </a>
          </div>
    
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-2xl font-bold text-white">
                {incident.affected_service}
              </h1>
              <span className="text-xs font-bold px-2 py-1 rounded bg-orange-500 text-white">
                {incident.severity}
              </span>
              <span className="text-xs px-2 py-1 rounded bg-blue-900 text-blue-300">
                {incident.status}
              </span>
            </div>
            <p className="text-gray-500 text-sm">
              {new Date(incident.created_at).toLocaleString()}
            </p>
          </div>
    
          {incident.root_cause && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Root Cause
              </h2>
              <p className="text-white mb-2">{incident.root_cause}</p>
              {incident.confidence_score && (
                <p className="text-green-400 text-sm">
                  {Math.round(incident.confidence_score * 100)}% confidence
                </p>
              )}
            </div>
          )}
          {/* Renders an ordered list of remediation steps. index + 1 converts 0-based index to 1-based for display. */}
          {incident.remediation_steps && incident.remediation_steps.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Remediation Steps
              </h2>
              <ol className="space-y-2">
                {incident.remediation_steps.map((step, index) => (
                  <li key={index} className="flex gap-3 text-sm text-gray-300">
                    <span className="text-gray-500 font-mono">{index + 1}.</span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
    
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
              Agent Reasoning
            </h2>
            {/* This is where the Server Component hands off to the Client Component. 
            The Server Component fetched the incident and knows its ID. 
            It passes the ID as a prop to AgentStream, 
            which opens the SSE connection in the browser. */}
            <AgentStream incidentId={incident.id} />
          </div>
        </main>
      )
    }
