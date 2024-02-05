import json
import os
import subprocess
import shutil
from Keyvalue import JsonKeys
from Result import Result
from report_builder import TableGenerator

issue_folder_dir = 'ISSUES'
specimin_input = 'input'
specimin_output = 'output'
specimin_project_name = 'specimin'
specimin_source_url = 'https://github.com/kelloggm/specimin.git'
TIMEOUT_DURATION = 300

def read_json_from_file(file_path):
    '''
    Parse a json file.

    Parameters:
        file_path (path): Path to the json file

    Retruns:
        { }: Parsed json data
    '''
    try:
        with open(file_path, 'r') as file:
            json_data = json.load(file)
        return json_data
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None


def get_repository_name(github_ssh: str):
    '''
    Extract the repository name from github ssh
    Parameters:
        github_ssh (str): A valid github ssh

    Returns: repository name 
    '''
    repository_name = os.path.splitext(os.path.basename(github_ssh))[0]
    return repository_name

def create_issue_directory(issue_container_dir, issue_id):
    '''
    Creates a directory to store a SPECIMIN target project. Example: issue_id of cf-111 will create
    a cf-111 directory inside 'issue_container_dir'. Two other directory (input and output inside) will
    be created inside 'issue_container_dir/issue_id' directory. Target project is cloned inside 
    'issue_container_dir/issue_id/input' directory. SPECIMIN output is stored inside 'issue_container_dir/issue_id/output'
    directory

    issue_container_dir
    |--- issue_id     
    |    |--- input
    |    |--- output 

    Parameters: 
        issue_container_dir (str): The directory where new directory is created
        issue_id (str): Name of the directory to be created

    Returns:
        specimin_input_dir (str): A target directory of SPECIMIN. (issue_container_dir/issue_id/input) 
    '''
    issue_directory_name = os.path.join(issue_container_dir, issue_id)
    os.makedirs(issue_directory_name, exist_ok=True)

    specimin_input_dir = os.path.join(issue_directory_name, specimin_input)
    specimin_output_dir = os.path.join(issue_directory_name, specimin_output)

    os.makedirs(specimin_input_dir, exist_ok=True)
    if os.path.exists(specimin_output):
        shutil.rmtree(specimin_output)
    os.makedirs(specimin_output_dir, exist_ok=True)
    return specimin_input_dir


def is_git_directory(dir):
    '''
    Check whether a directory is a git directory
    Parameters:
        dir: path of the directory
    Returns:
        booleans
    '''
    git_dir_path = os.path.join(dir, '.git')
    return os.path.exists(git_dir_path) and os.path.isdir(git_dir_path)

def clone_repository(url, directory):
    '''
    Clone a repository from 'url' in 'directory' 

    Parameters:
        url (str): repository url
        directory (str): directory to clone in
    '''
    project_name = get_repository_name(url)
    if (os.path.exists(f"{directory}/{project_name}")):
        print(f"{project_name} repository already exists. Aborting cloning")
        return
    subprocess.run(["git", "clone", url], cwd=directory)

def change_branch(branch, directory):
    '''
    Checkout a branch of a git repository

    Parameters:
        branch (str): branch name
        directory (str): local directory of the git repository
    '''
    if not is_git_directory(directory):
        raise ValueError(f"{directory} is not a valid git directory")
    command = ["git", "checkout", f"{branch}"]
    subprocess.run(command, cwd=directory)

def checkout_commit(commit_hash, directory):   
    '''
    Checkout a commit of a git repository

    Parameters:
        commit_hash (str): commit hash
        directory (str): local directory of the git repository
    '''
    if not is_git_directory(directory):
        raise ValueError(f"{directory} is not a valid git directory")
    
    command = ["git", "checkout", commit_hash]
    result = subprocess.run(command, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode == 0:
        print(f"Successfully checked-out commit {commit_hash} in {directory}")
    else:
        print(f"Failed to checkout commit {commit_hash} in {directory}")
    return result.returncode == 0 if True else False

def perform_git_pull (directory):
    '''
    Pull latest of a git repository

    Parameters:
        directory (str): local directory of the git repository
    '''
    command=["git", "pull", "origin", "--rebase"]
    subprocess.run(command, cwd=directory)

def clone_specimin(path_to_clone, url): 
    '''
    Clone the latest Specimin project from github

    Parameters:
        path_to_clone (str): Path where Specimin is to be clonned
        url (str): url of specimin
    '''
    spcimin_source_path = os.path.join(issue_folder_dir, specimin_project_name)
    if (os.path.exists(spcimin_source_path)) and os.path.isdir(spcimin_source_path):
        perform_git_pull(spcimin_source_path)
    else:
        clone_repository(url, path_to_clone)


def build_specimin_command(project_name: str,
                           issue_input_dir: str,
                           specimin_dir: str, 
                           root_dir: str,  
                           targets: list):
    '''
    Build the gradle command to execute Specimin on target project

    issue_container_dir(ISSUES)
    |--- issue_id(cf-1291)     
    |    |--- input  ---> it contains the git repository of a target project
    |    |      |----nomulus/core/src/main/java/    ---> this is the root directory of a package
    |    |                                   |---package_path/file.java (daikon/chicory/PureMethodInfo.java)  --> a target file
    |    |--- output --> Contains minimization result of Specimin

    
    Parameters:
        project_name (str): Name of the target project. Example: daikon
        issue_input_dir (str): path of the target project directory. Ex: ISSUES/cf-1291
        specimin_dir (str): Specimin directory path
        root_dir (str): A directory path relative to the project base directory where java package stored.
        targets ({'method': '', 'file': '', 'package': ''}) : target java file and method name data
    
    Retruns:
        command (str): The gradle command of SPECIMIN for the issue.
    '''

    relative_path_of_target_dir = os.path.relpath(issue_input_dir, specimin_dir)

    output_dir = os.path.join(relative_path_of_target_dir, specimin_output)
    root_dir = os.path.join(relative_path_of_target_dir, specimin_input, project_name, root_dir)
    root_dir = root_dir.rstrip('/') + os.sep

    target_file_list = []
    target_method_list = []

    for target in targets:

        method_name = target[JsonKeys.METHOD_NAME.value]
        file_name = target[JsonKeys.FILE_NAME.value]
        package_name = target[JsonKeys.PACKAGE.value]

        dot_replaced_package_name = package_name.replace('.', '/')

        if file_name:
            qualified_file_name = os.path.join(dot_replaced_package_name, file_name)
            target_file_list.append(qualified_file_name)

        if method_name:
            inner_class_name = ""
            if JsonKeys.INNER_CLASS.value in target and target[JsonKeys.INNER_CLASS.value] :
                inner_class_name = f".{target[JsonKeys.INNER_CLASS.value]}"
            
            qualified_method_name = package_name + "." + os.path.splitext(file_name)[0]+ inner_class_name + "#" + method_name
            target_method_list.append(qualified_method_name)

    output_dir_subcommand = "--outputDirectory" + " " + f"\"{output_dir}\""
    root_dir_subcommand = "--root" + " " + f"\"{root_dir}\""

    target_file_subcommand = ""
    for file in target_file_list:
        target_file_subcommand += "--targetFile" + " " + f"\"{file}\""

    target_method_subcommand = ""
    for method in target_method_list:
        target_method_subcommand += "--targetMethod" + " " + f"\"{method}\""

    command_args = root_dir_subcommand + " " + output_dir_subcommand + " " + target_file_subcommand + " " + target_method_subcommand
    command = "./gradlew" + " " + "run" + " " + "--args=" + f"\'{command_args}\'"
    
    return command

def run_specimin(issue_name, command, directory) -> Result:
    '''
    Execute SPECIMIN on a target project

    Parameters:
        command (str): The gradle command to run specimin
        directory (str): The base directory of the specimin repository
    
    Returns: 
        boolean: True/False based on successful execution of SPECIMIN
    '''
    try:
        result = subprocess.run(command, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, timeout=TIMEOUT_DURATION)
        if result.returncode == 0:
            return Result(issue_name, "PASS", "")
        else:
            error_msg_file = os.path.join(issue_folder_dir, issue_name, f"{issue_name}_error.txt")
            if os.path.exists(error_msg_file):
                os.remove(error_msg_file)
            with open(error_msg_file, 'w') as file:
                file.write(result.stderr.decode("utf-8"))
            return Result(issue_name, "FAIL", f"{error_msg_file}")
    except subprocess.TimeoutExpired:
        return Result(issue_name, "FAIL", "Timeout")
    except Exception as e:
        return Result(issue_name, "FAIL", f"Unhandled exception occurred: {e}")
    
    

def performEvaluation(issue_data) -> Result:
    '''
    For each issue data, execute SPECIMIN on a target project. 

    Parameters:
        issue ({}): json data associated with an issue    
    '''

    issue_id = issue_data[JsonKeys.ISSUE_ID.value]
    url = issue_data[JsonKeys.URL.value]
    branch = issue_data[JsonKeys.BRANCH.value]
    commit_hash = issue_data[JsonKeys.COMMIT_HASH.value]

    input_dir = create_issue_directory(issue_folder_dir, issue_id) # ../cf-12/input
    clone_repository(url, input_dir)  # TODO: check if clonning is successful.
    repo_name = get_repository_name(url)

    if branch:
        change_branch(branch, f"{input_dir}/{repo_name}")  
    
    if commit_hash:
        checkout_commit(commit_hash, f"{input_dir}/{repo_name}")

    specimin_command = build_specimin_command(repo_name, os.path.join(issue_folder_dir, issue_id), os.path.join(issue_folder_dir, specimin_project_name),issue_data[JsonKeys.ROOT_DIR.value], issue_data[JsonKeys.TARGETS.value])

    result = run_specimin(issue_id ,specimin_command, os.path.join(issue_folder_dir, specimin_project_name))
    print(f"{result.name} - {result.status}")
    return result


def main():
    '''
    Main method of the script. It iterates over the json data and perform minimization for each cases.   
    '''
    os.makedirs(issue_folder_dir, exist_ok=True)   # create the issue holder directory
    clone_specimin(issue_folder_dir, specimin_source_url)

    json_file_path = 'resources/test_data.json'
    parsed_data = read_json_from_file(json_file_path)

    evaluation_results = []
    if parsed_data:
        for issue in parsed_data:
            result = performEvaluation(issue)
            evaluation_results.append(result)


    report_generator = TableGenerator(evaluation_results)
    report_generator.generateTable()
    print("\n\n\n\n")
    print(f"issue_name    |    status    |    reason")
    print("--------------------------------------------")
    case = 1
    for minimization_result in evaluation_results:
        print(f"({case}){minimization_result.name}    |    {minimization_result.status}     |    {minimization_result.reason}")
        case +=1
    

if __name__ == "__main__":
    main()