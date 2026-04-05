import re

with open("templates/frontend/index.html", "r", encoding="utf-8") as f:
    text = f.read()

new_form = """        <button id="huntBtn" type="button" class="px-6 py-2 text-xs font-headline font-bold uppercase tracking-widest bg-yellow-500/20 text-yellow-400 border border-yellow-500/50 hover:bg-yellow-500/40 glow-primary transition-transform active:scale-95 flex gap-2 items-center">
            <span class="material-symbols-outlined text-[14px]" id="huntIcon">travel_explore</span>
            <span id="huntText">Initiate AI Hunt</span>
        </button>

<div id="huntModal" class="hidden fixed inset-0 z-50 flex items-center justify-center bg-background/90 backdrop-blur-sm">
    <div class="glass-panel border-primary/50 border p-8 max-w-2xl w-full rounded-sm shadow-2xl">
        <h3 class="font-headline text-xl text-primary font-bold mb-4 flex items-center gap-2">
            <span class="material-symbols-outlined animate-spin text-primary">cyclone</span> RADAR SWEEP ACTIVE
        </h3>
        <div id="huntLogs" class="bg-[#0a0a0a] p-6 font-mono text-[11px] text-green-400 h-64 overflow-y-auto space-y-2 rounded-sm border border-primary/20 flex flex-col gap-1 shadow-inner">
            <!-- Logs go here -->
        </div>
        <button id="closeHuntModal" class="hidden mt-6 w-full py-3 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/30 text-xs tracking-widest uppercase font-headline glow-primary transition-all duration-300">Reload Radar Feed</button>
    </div>
</div>

<script>
document.getElementById('huntBtn').addEventListener('click', function() {
    this.disabled = true;
    const icon = document.getElementById('huntIcon');
    icon.classList.add('animate-spin');
    icon.innerText = 'cyclone';
    
    document.getElementById('huntModal').classList.remove('hidden');
    const logs = document.getElementById('huntLogs');
    logs.innerHTML = '<div class="text-on-surface-variant">Establishing uplink to Jobicy Data Hub...</div>';
    
    const source = new EventSource('/api/hunt/stream');
    
    source.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.done) {
            source.close();
            logs.innerHTML += '<div class="text-yellow-400 mt-4 font-bold text-sm">SWEEP COMPLETE. Background Workers engaged.</div>';
            document.getElementById('closeHuntModal').classList.remove('hidden');
            
            icon.classList.remove('animate-spin');
            icon.innerText = 'travel_explore';
            document.getElementById('huntBtn').disabled = false;
            return;
        }
        
        const line = document.createElement('div');
        line.innerText = '> ' + data.message;
        logs.appendChild(line);
        logs.scrollTop = logs.scrollHeight;
    };
    
    source.onerror = function() {
        source.close();
        document.getElementById('closeHuntModal').classList.remove('hidden');
    };
});

document.getElementById('closeHuntModal').addEventListener('click', () => {
    window.location.reload();
});
</script>"""

old_str = '''            <form action="/api/hunt" method="POST">
                <button type="submit" class="px-6 py-2 text-xs font-headline font-bold uppercase tracking-widest bg-yellow-500/20 text-yellow-400 border border-yellow-500/50 hover:bg-yellow-500/40 glow-primary transition-transform active:scale-95 flex gap-2 items-center">
                    <span class="material-symbols-outlined text-[14px]">travel_explore</span>
                    Initiate AI Hunt
                </button>
            </form>'''

if old_str in text:
    text = text.replace(old_str, new_form)
    with open("templates/frontend/index.html", "w", encoding="utf-8") as f:
        f.write(text)
    print("Patched index.html")
else:
    print("Could not find block in index.html. Did it change?")