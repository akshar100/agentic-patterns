import sys, os, re

PATTERN_MAP = {
    "reason-act": ("Reason%20%26%20Act", "blue"),
    "plan-then-execute": ("Plan%20Then%20Execute", "blue"),
    "search-over-actions": ("Search%20Over%20Actions", "blue"),
    "reflection": ("Reflection", "blue"),
    "code-as-action": ("Code%20As%20Action", "blue"),
    "orchestrator-worker": ("Orchestrator%20Worker", "green"),
    "peer-debate": ("Peer%20Debate", "green"),
    "role-based-teams": ("Role%20Based%20Teams", "green"),
    "conversational": ("Conversational", "green"),
    "handoff": ("Handoff", "green"),
    "context-management": ("Context%20Management", "orange"),
    "episodic-memory": ("Episodic%20Memory", "orange"),
    "shared-memory": ("Shared%20Memory", "orange"),
    "checkpointing": ("Checkpointing", "orange"),
    "human-in-loop": ("Human%20in%20Loop", "purple"),
}

DETECTION_RULES = {
    "reason-act": [r"Thought:.*Action:", r"ReAct", r"AgentExecutor"],
    "plan-then-execute": [r"plan_and_execute", r"Plan:.*Execute:", r"DAGPlanner"],
    "search-over-actions": [r"Tree of Thoughts", r"LATS", r"mcts"],
    "reflection": [r"Reflexion", r"Self-Refine", r"critic.*feedback"],
    "code-as-action": [r"PythonREPL", r"code_interpreter", r"CodeAct", r"exec_code"],
    "orchestrator-worker": [r"orchestrator", r"subtask.*worker", r"delegate_to_worker"],
    "peer-debate": [r"multi_agent_debate", r"agent_as_judge", r"aggregate_votes"],
    "role-based-teams": [r"MetaGPT", r"ChatDev", r"role_prompt"],
    "conversational": [r"GroupChatManager", r"AutoGen", r"shared_transcript"],
    "handoff": [r"transfer_to", r"Agent2Agent", r"A2A", r"handoff_tool", r"a2a-protocol"],
    "checkpointing": [r"checkpointer", r"MemorySaver", r"save_state", r"resume_from"],
    "human-in-loop": [r"interrupt_before", r"human_approval", r"ask_user_for_input"]
}

def scan_codebase(target_dir):
    detected = set()
    skip = {'.git', 'node_modules', 'venv', '__pycache__'}
    exts = {'.py', '.ts', '.js', '.java', '.go'}
    
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in skip]
        for file in files:
            if not any(file.endswith(e) for e in exts): continue
            try:
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    content = f.read()
                    for p, rules in DETECTION_RULES.items():
                        if p in detected: continue
                        if any(re.search(r, content, re.IGNORECASE) for r in rules):
                            detected.add(p)
            except: pass
    return list(detected)

def generate_badges(patterns):
    badges = []
    for p in sorted(patterns):
        if p in PATTERN_MAP:
            lbl, col = PATTERN_MAP[p]
            badges.append(f"![{p}](https://img.shields.io/badge/Agentic_Pattern-{lbl}-{col}?style=flat-square)")
    return "\n".join(badges) if badges else "*No agentic patterns detected.*"

def update_readme(readme_path, new_badges):
    if not os.path.exists(readme_path): 
        print(f"Error: {readme_path} not found.")
        return
        
    with open(readme_path, 'r', encoding='utf-8') as f: 
        content = f.read()
        
    start, end = "<!-- AGENTIC_BADGES_START -->", "<!-- AGENTIC_BADGES_END -->"
    pat = re.compile(f"{start}.*?{end}", re.DOTALL)
    
    if not pat.search(content): 
        print("Markers not found in README.")
        return
        
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(pat.sub(f"{start}\n{new_badges}\n{end}", content))

if __name__ == "__main__":
    if len(sys.argv) == 3:
        badges = generate_badges(scan_codebase(sys.argv[1]))
        update_readme(sys.argv[2], badges)
