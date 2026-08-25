interface Incident {
  id: string;
  affected_service: string;
  severity: string;
  status: string;
  root_cause: string | null;
  confidence_score: number | null;
  created_at: string;
  updated_at: string;
}

async function getIncidents(): Promise<Incident[]> {
  try {
    const response = await fetch("http://localhost:8000/incidents/", {
      cache: "no-store",
    });
    if (!response.ok) return [];
    return response.json();
  } catch (error) {
    return [];
  }
}

function getSeverityColor(severity: string): string {
  switch (severity) {
    case "P0": return "bg-red-500 text-white";
    case "P1": return "bg-orange-500 text-white";
    case "P2": return "bg-yellow-500 text-black";
    case "P3": return "bg-blue-500 text-white";
    default:   return "bg-gray-500 text-white";
  }
}

function getStatusColor(status: string): string {
  switch (status) {
    case "detected":      return "bg-gray-700 text-gray-300";
    case "investigating": return "bg-blue-900 text-blue-300";
    case "resolved":      return "bg-green-900 text-green-300";
    case "false_alarm":   return "bg-purple-900 text-purple-300";
    default:              return "bg-gray-700 text-gray-300";
  }
}

export default async function IncidentsPage() {
  const incidents = await getIncidents();

  return (
    <main className="max-w-5xl mx-auto px-6 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">
          Incident Whisperer
        </h1>
        <p className="text-gray-400">
          Autonomous on-call agent system — real-time incident diagnosis
        </p>
      </div>

      {incidents.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-lg">No incidents yet</p>
          <p className="text-sm mt-2">
            Trigger one via POST /incidents to get started
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {incidents.map((incident) => (
            <a
              key={incident.id}
              href={`/incidents/${incident.id}`}
              className="block bg-gray-900 border border-gray-800 rounded-xl p-6 hover:border-gray-600 transition-colors"
            >
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-semibold text-white">
                  {incident.affected_service}
                </h2>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold px-2 py-1 rounded ${getSeverityColor(incident.severity)}`}>
                    {incident.severity}
                  </span>
                  <span className={`text-xs px-2 py-1 rounded ${getStatusColor(incident.status)}`}>
                    {incident.status}
                  </span>
                </div>
              </div>

              {incident.root_cause ? (
                <p className="text-gray-300 text-sm mb-3">
                  {incident.root_cause}
                </p>
              ) : (
                <p className="text-gray-500 text-sm mb-3 italic">
                  Analyzing...
                </p>
              )}

              <div className="flex items-center justify-between text-xs text-gray-500">
                <span>
                  {new Date(incident.created_at).toLocaleString()}
                </span>
                {incident.confidence_score && (
                  <span className="text-green-400">
                    {Math.round(incident.confidence_score * 100)}% confidence
                  </span>
                )}
              </div>
            </a>
          ))}
        </div>
      )}
    </main>
  );
}
