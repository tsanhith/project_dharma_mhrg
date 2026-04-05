import os
import json
import subprocess
from celery import shared_task
from database.db import SessionLocal
from database.models import JobPipeline, JobStatus, UserProfile
from worker import celery_app
from groq import Groq
from jinja2 import Environment, FileSystemLoader
import pydantic

# Strictly define what we want from the LLM
class BulletPoints(pydantic.BaseModel):
    summary: str
    bullets: list[str]

@celery_app.task(name='agents.tailor.tailor_resume', bind=True)
def tailor_resume(self, job_id: str):
    """The Surgeon: Reads SCRAPED data, calls Groq LLM, creates JSON, injects into Jinja2 LaTeX, and compiles the PDF."""
    print(f"[SURGEON] Initiating tailor for Job ID: {job_id}")
    db = SessionLocal()
    
    try:
        # 1. Fetch Job from DB
        job = db.query(JobPipeline).filter(JobPipeline.id == job_id).first()
        if not job or job.status != JobStatus.SCRAPED:
            print(f"[SURGEON] Job {job_id} is not SCRAPED or not found. Skipping.")
            return

        profile = db.query(UserProfile).first()
        if not profile:
            print(f"[SURGEON] No UserProfile found. Cannot tailor.")
            return

        print(f"[SURGEON] Connecting to NVIDIA GLM5 via free API for {job.url}...")    

        # 2. Free LLM Surgery
        prompt = f"""You are an expert ATS resume writer. I am giving you the raw text of a job description and the user's base resume.
        Extract a powerful 2-sentence summary and exactly 4 optimized bullet points matching the required skills based on the user's experience.
        DO NOT use any markdown, LaTeX symbols, or extra text. Output ONLY valid JSON matching this schema:
        {{ "summary": "string", "bullets": ["str", "str", "str", "str"] }}      

        USER BASE RESUME TEXT:
        {profile.base_resume_text[:2000] if profile.base_resume_text else 'None'}

        RAW JOB TEXT:
        {(job.raw_jd_text or "")[:3000]}  # Slicing to 3k characters to save context window
        """

        try:
            from openai import OpenAI
            import sys
            
            _USE_COLOR = sys.stdout.isatty() and os.getenv("NO_COLOR") is None
            _REASONING_COLOR = "\033[90m" if _USE_COLOR else ""
            _RESET_COLOR = "\033[0m" if _USE_COLOR else ""
            
            nvidia_client = OpenAI(
              base_url = "https://integrate.api.nvidia.com/v1",
              api_key = "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" # Or os.getenv("NVIDIA_API_KEY")
            )
            
            completion = nvidia_client.chat.completions.create(
              model="z-ai/glm5",
              messages=[
                  {"role": "system", "content": "You are a JSON-only API. You output raw valid JSON without markdown wrapping."},
                  {"role": "user", "content": prompt}
              ],
              temperature=1,
              top_p=1,
              max_tokens=4096,
              extra_body={"chat_template_kwargs":{"enable_thinking":True,"clear_thinking":False}},
              stream=True
            )
            
            llm_response = ""
            for chunk in completion:
              if not getattr(chunk, "choices", None):
                continue
              if len(chunk.choices) == 0 or getattr(chunk.choices[0], "delta", None) is None:
                continue
              delta = chunk.choices[0].delta
              reasoning = getattr(delta, "reasoning_content", None)
              if reasoning:
                print(f"{_REASONING_COLOR}{reasoning}{_RESET_COLOR}", end="", flush=True)
              if getattr(delta, "content", None) is not None:
                print(delta.content, end="", flush=True)
                llm_response += delta.content
            print() # Next line after stream finishes
            
            # Z-AI/GLM5 output might be wrapped in ```json ... ``` despite instructions. Clean it.
            if "```json" in llm_response:
                llm_response = llm_response.split("```json")[1].split("```")[0].strip()
            elif "```" in llm_response:
                llm_response = llm_response.split("```")[1].split("```")[0].strip()
                
        except Exception as nvidia_e:
            print(f"[SURGEON] NVIDIA GLM5 failed: {nvidia_e}. Falling back to Groq...")
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))

            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a JSON-only API. You output raw valid JSON without markdown wrapping."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.1-8b-instant",
                response_format={"type": "json_object"}
            )
            llm_response = chat_completion.choices[0].message.content

        print(f"[SURGEON] LLM Response received!")
        
        # 3. Strict Pydantic Validation of LLM output
        structured_data = BulletPoints.model_validate_json(llm_response)

        # 4. LaTeX Injection (Jinja2)
        print(f"[SURGEON] Writing data to LaTeX template...")
        
        # Configure Jinja2 to avoid LaTeX syntax blocks ({}, %, #)
        env = Environment(
            loader=FileSystemLoader("templates"),
            block_start_string="<%",
            block_end_string="%>",
            variable_start_string="<<",
            variable_end_string=">>",
            comment_start_string="<#",
            comment_end_string="#>",
            trim_blocks=True,
            autoescape=False
        )
        
        template = env.get_template("base_resume.tex")
        
        # Clean extracted bullets of latex-breaking characters
        safe_bullets = [b.replace("&", r"\&").replace("%", r"\%") for b in structured_data.bullets]
        safe_summary = structured_data.summary.replace("&", r"\&").replace("%", r"\%")
        
        # Render LaTeX content
        rendered_tex = template.render(
            candidate_name=profile.name or "JOHN DOE",
            location=profile.location or "San Francisco, CA",
            phone=profile.phone or "(555) 123-4567",
            email=profile.email or "johndoe@example.com",
            linkedin_url=profile.linkedin_url or "https://linkedin.com/in/johndoe",
            github_url=profile.github_url or "https://github.com/johndoe",
            portfolio_url=profile.portfolio_url or "https://johndoe.dev",
            job_title=job.title,
            company=job.company,
            summary=safe_summary,
            bullets=safe_bullets
        )
        
        # Save exact tex file for debugging and compilation
        os.makedirs("output_pdfs", exist_ok=True)
        tex_path = os.path.join(os.getcwd(), f"output_pdfs", f"resume_{job_id}.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(rendered_tex)

        print("[SURGEON] Compiling LaTeX via pdflatex...")
        try:
            # pdflatex has to be invoked in the target directory to stash its auxiliary junk
            compile_process = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", f"resume_{job_id}.tex"],
                cwd=os.path.join(os.getcwd(), "output_pdfs"),
                capture_output=True,
                text=True,
                timeout=15 
            )
            if compile_process.returncode != 0:
                print(f"[SURGEON] Warning: pdflatex compilation exited with code {compile_process.returncode}. PDF may not have generated correctly or syntax was flawed.")
                print(compile_process.stdout)
        except subprocess.TimeoutExpired:
            print("[SURGEON] ERROR: LaTeX compilation hung permanently. Killing Subprocess to protect loop.")
            raise Exception("pdflatex infinite loop triggered")
        
        # 5. Database Update (Success)
        job.status = JobStatus.TAILORING
        db.commit()
        
        print(f"[SURGEON] Successfully extracted bullets. Pushing to Command Center Queue...")
        
        # 6. Hand-off to the Notion Sync Agent
        celery_app.send_task('agents.notion_sync.sync_to_notion', args=[job_id], queue='sync_queue')

    except pydantic.ValidationError as ve:
        print(f"[SURGEON-ERROR] LLM hallucinated bad JSON: {ve}")
        if 'job' in locals() and job:
            job.status = JobStatus.ERROR
            job.error_message = f"LLM returned invalid JSON: {str(ve)}"
            db.commit()
    except Exception as e:
        print(f"[SURGEON-ERROR] Failed to tailor {job_id}: {str(e)}")
        if 'job' in locals() and job:
            job.status = JobStatus.ERROR
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()
