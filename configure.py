#!/usr/bin/env python3
"""Create a safe starter configuration for Pi Service Doctor."""
from __future__ import annotations
import argparse, json, socket, subprocess
from pathlib import Path

COMMON_SERVICES = (("nginx","nginx web server"),("apache2","Apache web server"),("ssh","Secure shell"),("sshd","Secure shell"),("docker","Docker"),("mosquitto","Mosquitto MQTT"),("tailscaled","Tailscale"),("cloudflared","Cloudflare Tunnel"),("home-assistant","Home Assistant"))
COMMON_TIMERS = (("apt-daily.timer","Package metadata updates"),("apt-daily-upgrade.timer","Automatic package upgrades"),("logrotate.timer","Log rotation"),("fstrim.timer","Filesystem trim"))

def unit_exists(name):
    result=subprocess.run(["systemctl","show",name,"--property=LoadState","--value"],capture_output=True,text=True,check=False)
    return result.returncode==0 and result.stdout.strip() not in {"","not-found"}

def unit_active(name):
    return subprocess.run(["systemctl","is-active","--quiet",name],check=False).returncode==0

def discover():
    services=[]
    seen_labels=set()
    for name,label in COMMON_SERVICES:
        if label not in seen_labels and unit_exists(name) and unit_active(name):
            services.append({"name":name,"label":label,"required":True})
            seen_labels.add(label)
    timers=[{"name":n,"label":l,"required":False} for n,l in COMMON_TIMERS if unit_exists(n) and unit_active(n)]
    web=any(x["name"] in {"nginx","apache2"} for x in services)
    return {"name":socket.gethostname(),"diskPath":"/","thresholds":{"diskWarningPercent":80,"diskCriticalPercent":92,"memoryWarningPercent":85,"memoryCriticalPercent":95,"temperatureWarningC":72,"temperatureCriticalC":80,"fileWarningHours":24},"services":services,"timers":timers,"ports":[{"host":"127.0.0.1","port":80,"label":"Local web server","required":False}] if web else [],"urls":[{"url":"http://127.0.0.1/","label":"Local home page","expected":[200],"required":False}] if web else [],"files":[],"ignoreFailedUnits":["run-*.service"]}

def ask(message,default=True):
    answer=input(f"{message} {'[Y/n]' if default else '[y/N]'} ").strip().lower()
    return default if not answer else answer in {"y","yes"}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output",type=Path,default=Path("config.json"));parser.add_argument("--non-interactive",action="store_true");parser.add_argument("--force",action="store_true");args=parser.parse_args()
    if args.output.exists() and not args.force: print(f"Keeping existing configuration: {args.output}");return 0
    config=discover()
    if not args.non_interactive:
        print("\nDiscovered services and timers. Choose what should appear in the report.\n")
        config["services"]=[x for x in config["services"] if ask(f'Monitor service “{x["label"]}”?')]
        config["timers"]=[x for x in config["timers"] if ask(f'Monitor timer “{x["label"]}”?')]
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(config,indent=2)+"\n",encoding="utf-8")
    print(f"Configuration written to {args.output}");print(f"Discovered {len(config['services'])} services, {len(config['timers'])} timers and {len(config['urls'])} web routes.");return 0

if __name__=="__main__": raise SystemExit(main())
