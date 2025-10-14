from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import Dict, Any, List
import subprocess
import asyncio
import tempfile
import logging
import os
from model import Problems, TestCases
from config import LANGUAGE_CONFIG, TIME_LIMIT, MEMORY_LIMIT

async def run_code_in_nsjail(cmd:List[str], cwd_path:str, input_data:str, time_limit:str) -> Dict[str, Any]:
    """
    A function the grades user submitted code
    Execution code in nsjail sandbox
    Args:
    Returns: 
    """
    if not input_data.endswith('\n'):
            input_data += '\n'
    input_data = input_data.rstrip('\r\n') + '\n'
    nsjail_base_cmd = [
        '/usr/local/bin/nsjail',
        '--mode', 'o', # Run once and quit
        '--quiet',
        '--log', '/dev/null',
        '--time_limit', str(time_limit),
        '--rlimit_as', str(MEMORY_LIMIT),
        '--disable_clone_newnet', 
        '--bindmount', '/usr/bin:/usr/bin',
        '--bindmount', '/usr/lib:/usr/lib',
        '--bindmount', '/lib:/lib',
        '--bindmount', '/lib64:/lib64',
        '--bindmount', f"{cwd_path}:/app",
        '--cwd', '/app',
        '--',
    ]
    full_cmd = nsjail_base_cmd + cmd
    try:
        process = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=input_data.encode()),
            timeout=TIME_LIMIT + 1 # Consider process communication time
        )
        if stderr:
            print("NSJAIL stderr:", stderr.decode(errors='ignore'))
        if process.returncode == 1000 + 10: # ETIME (Time expired)
            return {"status": "Time Limit Exceeded"}
        
        return {
            "return_code" : process.returncode,
            "stdout" : stdout.decode(errors='ignore'),
            "stderr" : stderr.decode(errors='ignore')
        }
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return {"status" : "Time Limit Exceeded"}
    
    except Exception as e:
        logging.error(f"Sandbox execution failed: {e}")
        return {"status" : "Runtime Error", "message" : {str(e)}}

async def grading_code_challenge(job_data:Dict[str,Any], session:AsyncSession)->Dict[str,Any]:
    """
    Grading user submitted code using by nsjail sandox 
    """
    language = job_data.get("language")
    code = job_data.get("code")
    problem_id = job_data.get("problem_id")
    
    config = LANGUAGE_CONFIG.get(language)
    if not config:
        return {"status" : "System Error", "message" : "Unsupported language"}
    
    query = select(Problems).where(Problems.problem_id == problem_id).options(selectinload(Problems.test_cases))
    #query = select(Problems).where(Problems.problem_id==problem_id)
    result = await session.execute(query)
    problem = result.scalar_one_or_none()
    print(f"Problem id : {problem.problem_id}")
    if not problem or not problem.test_cases:
        return {"status" : "System Error", "message" : "Problem or test cases not found"}
    
    tc_query = select(TestCases).where(TestCases.problem_id == problem.problem_id + 1)
    tc_result = await session.execute(tc_query)
    test_cases = tc_result.scalars().all()
    print(f"TestCase:{test_cases}")
    if not test_cases:
        return {"status" : "System Error", "message" : "No test cases not found for problem"}
    
    problem.test_cases = test_cases
    
    with tempfile.TemporaryDirectory() as temp_dir:
        source_file = config['source_file']
        file_path = os.path.join(temp_dir, source_file)
        
        with open(file_path,'w') as f:
            f.write(code)
        
        if config['compile_cmd']:
            compile_result = await run_code_in_nsjail(config['compile_cmd'], cwd_path=temp_dir, input_data="", time_limit=5)
            if compile_result.get("return_code") != 0:
                return {"status" : "Compile Error", "message" : compile_result.get("stderr")}
            
        max_time = 0.0
        # tc: test case
        # i: index
        for i, tc in enumerate(problem.test_cases):
            input_data = tc.input_data.encode('utf-8').decode('unicode_escape').strip('"')
            print(f"[DEBUG] Test case {i+1} input:\n{repr(input_data)}")
            run_start_time = asyncio.get_event_loop().time()
            exec_result = await run_code_in_nsjail(config['run_cmd'], cwd_path=temp_dir, input_data=input_data, time_limit=TIME_LIMIT)
            run_end_time = asyncio.get_event_loop().time()
            max_time = max(max_time, run_end_time - run_start_time)

            if exec_result.get("status") == "Time Limit Exceeded":
                return {"status": "Time Limit Exceeded", "failed_case": i + 1}
            if exec_result.get("return_code") != 0:
                return {"status": "Runtime Error", "failed_case": i + 1, "message": exec_result.get("stderr")}
            
            user_output = exec_result.get("stdout", "").strip().replace('\r\n', '\n')
            correct_output = tc.output_data.encode('utf-8').decode('unicode_escape').strip('"')
            correct_output = correct_output.replace('\r\n', '\n')
            print(f"user_output: {repr(user_output)}")
            print(f"correct_output:{repr(correct_output)}")
            if user_output.strip() != correct_output.strip():
                return {"status": "Wrong Answer", "failed_case": i + 1}
        
        return {"status": "Accepted", "execution_time": round(max_time, 4)}

async def process_challenge_job(job_data:Dict[str,Any], session:AsyncSession, rmq_client):
    final_result = await grading_code_challenge(job_data, session)
    result_message = {
        "submission_id" : job_data.get("submission_id"),
        "result" : final_result
    }
    await rmq_client.publish_message("code_execution_queue", result_message)
    
    