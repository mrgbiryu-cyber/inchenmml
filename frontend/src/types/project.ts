export interface AgentDefinition {
    agent_id: string;
    role: string;
    model: string;
    provider: 'OPENROUTER' | 'OLLAMA';
    system_prompt: string;
    next_agents: string[];
}

export interface ProjectAgentConfig {
    workflow_type: 'SEQUENTIAL' | 'PARALLEL' | 'CUSTOM';
    agents: AgentDefinition[];
    entry_agent_id: string;
}

export interface Project {
    id: string;
    name: string;
    description?: string;
    project_type: 'EXISTING' | 'NEW';
    repo_path?: string;
    tenant_id: string;
    user_id: string;
    created_at: string;
    updated_at: string;
    agent_config?: ProjectAgentConfig;
}
