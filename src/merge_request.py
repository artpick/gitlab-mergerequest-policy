import json
import sys
import urllib
import urllib2
import time

from urllib2 import HTTPError

# static variables for reuse purpose
# This is the private token used to create the merge request and validate it.
http_header = {'PRIVATE-TOKEN': 'DDDDD'}

base_url_gitlab_api = 'http://<GITLAB_URL>:<GITLAB_PORT>/api/v3/{}'

project_search_parameter = 'projects?search={}'
project_merge_url = 'projects/{}/merge_requests'
project_get_merge_url = 'projects/{}/merge_requests/{}'
project_accept_merge_url = 'projects/{}/merge_requests/{}/merge'
project_tag_url = 'projects/{}/repository/tags'


class BranchInfoBean:
    """Class Branch info bean which stores the dev and rc branch names:
    - dev branch name
    - rc branch name"""

    def __init__(self, dev_branch_name, rc_branch_name):
        """Default constructor, this class must only contains the dev_branch_name and rc_branch_name attribute"""
        self.dev_branch_name = dev_branch_name
        self.rc_branch_name = rc_branch_name


# Function to craft to craft the full url
def craft_full_url(tail_url):
    return base_url_gitlab_api.format(tail_url)


# Exception printing rule
def exception_printing(exception, extra_title=None):
    if extra_title != None:
        print extra_title
    print 'Exception HTTP Error: {},  : {}'.format(exception.code, exception.msg)
    exit(1)


# Search the project to get the gitlab id
# - project_ssh_url
def find_gitlab_project_id(project_ssh_url):
    #
    index_of_slash = project_ssh_url.find('/') + 1

    #
    git_project = project_ssh_url[index_of_slash:len(project_ssh_url) - 4]

    #
    print 'The gitlab project you are trying to tag is {}'.format(git_project)

    # Prepare the request to find the project ID
    url_find_project = craft_full_url(project_search_parameter.format(git_project))
    request_get_project_by_name = urllib2.Request(url=url_find_project,
                                                  headers=http_header)
    # Execute the request and parse the JSON object.
    json_project_found = json.loads(urllib2.urlopen(request_get_project_by_name).read())
    # Whe have found some projects
    if len(json_project_found) > 0:
        # Filter by "ssh_url_to_repo" to make sure we found the good one
        found_project = filter(lambda x: x['ssh_url_to_repo'] == project_ssh_url, json_project_found)

        # Get the first just in case.
        first_found_project = found_project[0]

        print 'I have found the project {}, it was modified the last time on the {}.'.format(
            first_found_project['name'],
            first_found_project['last_activity_at'])

        # Retrieve the project ID
        return first_found_project['id']

    else:
        print 'No project with the name {} found.'.format(project_ssh_url)
        exit(1)

    return None


#
# Function that handle the tag policy:
#  - In any case we delete the tag (even it does not exist)
#  - Then we create one.
#
def tag_policy(project_version, gitlab_project_id, branch_infos):
    # Create the tag name
    tag_name = 'v' + project_version + '.rc'
    print 'We will create the tag: ' + tag_name
    #
    print '== Delete the maybe existing tag: ' + tag_name
    tag_after_merge_url = craft_full_url(
        project_tag_url.format(gitlab_project_id))

    tag_delete_url = tag_after_merge_url + '/' + tag_name

    try:
        request_delete_tag = urllib2.Request(
            tag_delete_url,
            None,
            http_header)

        # It has to be a 'DELETE'
        request_delete_tag.get_method = lambda: 'DELETE'

        urllib2.urlopen(request_delete_tag)

    except HTTPError, ex_crt_tag:
        # Handle the HttpErrors,
        delete_tag_result = json.loads(ex_crt_tag.read())
        # In that case, we don't know what happened.
        if delete_tag_result['message'] != 'No such tag':
            exception_printing(ex_crt_tag,
                               'Something wrong happened. While trying to create the tag: {} '.format(ex_crt_tag.code))
        else:
            # Here the tag does not exist.
            print 'The tag {} does not exists.'.format(tag_name)

    print '== Create the tag: {}.'.format(tag_name)

    # Create the tag.
    # Check if the tag is already present
    data_to_send_for_tag_creation = {'id': gitlab_project_id,
                                     'tag_name': tag_name,
                                     'ref': branch_infos.rc_branch_name,
                                     'message': 'Release tag {}.'.format(tag_name)}

    request_tag = urllib2.Request(
        url=tag_after_merge_url,
        data=urllib.urlencode(data_to_send_for_tag_creation),
        headers=http_header)
    tag_creation_result = json.loads(urllib2.urlopen(request_tag).read())

    print '== The tag policy ended with: {}'.format(tag_creation_result['name'])


# Accept merge request
# - gitlab_project_id
# - merge_request_infos
# - branch_infos
def accept_merge_request(gitlab_project_id, merge_request_infos, branch_infos):
    # Get the merge request id
    merge_request_id = merge_request_infos['id']
    print '== We accept the merge request if the pipeline succeeds.'
    # Craft the merge URL to update it as an accept merge request when the pipeline succeed.
    accept_mr_url = craft_full_url(
        project_accept_merge_url.format(gitlab_project_id, merge_request_id))
    # Data to send when accept succeed
    data_to_send_for_merge_when_succeed = {'merge_when_build_succeeds': True}

    # Create the put request to accept the mr in case the pipeline succeed.
    request_accept_merge_when_succeed = urllib2.Request(url=accept_mr_url,
                                                        data=urllib.urlencode(
                                                            data_to_send_for_merge_when_succeed),
                                                        headers=http_header)
    # It has to be a 'PUT'
    request_accept_merge_when_succeed.get_method = lambda: 'PUT'
    try:
        # Run the request to merge accept when the build succeed
        accepted_merge_info = json.loads(urllib2.urlopen(request_accept_merge_when_succeed).read())

        print '== The merge request will be accepted when th pipeline succeeds.'
        print '==== The merge when pipeline succeeds flag is set to : {}'.format(
            accepted_merge_info['merge_when_build_succeeds'])

    except HTTPError, exception:
        if exception.code == 405:
            exception_printing(exception, ' /!\ You have already merged {} with {}'.format(branch_infos.dev_branch_name,
                                                                                           branch_infos.rc_branch_name))
        else:
            exception_printing(exception)
    finally:
        wait_mr_url = craft_full_url(project_get_merge_url.format(gitlab_project_id, merge_request_id))
        request_get_mr_by_id = urllib2.Request(url=wait_mr_url,
                                                headers=http_header)
        # Execute the request and parse the JSON object.
        json_mr_found = json.loads(urllib2.urlopen(request_get_mr_by_id).read())
        while not('merged' == json_mr_found['state'] or 'closed' == json_mr_found['state']):
            # Sleep 1 minute
            time.sleep(60)
            # Then recall
            json_mr_found = json.loads(urllib2.urlopen(request_get_mr_by_id).read())
            print '== The merge request is accepted and merged or closed: {}'.format(json_mr_found['state'])

        print '== The merge request is accepted and merged or closed: {}'.format(json_mr_found['state'])

# Create the merge request
# - gitlab_project_id
# - project_version
# - branch_infos
def create_merge_request(gitlab_project_id, project_version, branch_infos):
    #
    # Create the merge request
    #
    print 'We will create the merge request from {} to {}'.format(branch_infos.dev_branch_name,
                                                                  branch_infos.rc_branch_name)
    # Replace the parametrized values
    create_mr_url = craft_full_url(project_merge_url.format(gitlab_project_id))
    # Prepare the datas to send the merge request creation
    title_mr = 'Merge {} to {}.'.format(branch_infos.dev_branch_name, branch_infos.rc_branch_name)

    description_mr = 'Merge the {} to {} to create the version: {}.'.format(
        branch_infos.dev_branch_name, branch_infos.rc_branch_name, project_version)

    data_to_send_for_mr_creation = {'source_branch': branch_infos.dev_branch_name,
                                    'target_branch': branch_infos.rc_branch_name,
                                    'title': title_mr,
                                    'description': description_mr}

    # Prepare the request to send the merge request creation
    request_create_merge = urllib2.Request(
        url=create_mr_url,
        data=urllib.urlencode(data_to_send_for_mr_creation),
        headers=http_header)
    print '== Create the merge request.'
    # Shipping to boston
    try:
        merge_request_infos = json.loads(urllib2.urlopen(request_create_merge).read())
        print '== The merge request from {} to {} have been created with the title \'{}\''.format(
            merge_request_infos['source_branch'],
            merge_request_infos['target_branch'],
            merge_request_infos['title'])

        print '==== The merge status is: {}'.format(merge_request_infos['merge_status'])
        print '==== The state is: {}'.format(merge_request_infos['state'])
        print '==== The merge when pipeline succeeds flag is set to : {}'.format(
            merge_request_infos['merge_when_build_succeeds'])

        return merge_request_infos

    except HTTPError, exception:
        if exception.code == 409:
            exception_printing(exception, '==== /!\ You have a merge conflict issue FIX IT. ====')
        else:
            exception_printing(exception)

    return None


# Main programm
def main(argv):
    if len(argv) == 5:
        # Get the project name and version in parameter
        project_ssh_url = argv[1]
        project_version = argv[2]
        dev_branch_name = argv[3]
        rc_branch_name = argv[4]

        branch_infos = BranchInfoBean(dev_branch_name, rc_branch_name)

        # Find the gitlab id, so we can manipulate the project
        gitlab_project_id = find_gitlab_project_id(project_ssh_url)

        # Create the merge request
        merge_request_infos = create_merge_request(gitlab_project_id, project_version, branch_infos)

        # Accept the merge request
        accept_merge_request(gitlab_project_id, merge_request_infos, branch_infos)

        # Handle the tag policy.
        tag_policy(project_version, gitlab_project_id, branch_infos)

        exit(0)

    else:
        print 'There\'s a missing argument; length is:' + len(argv)
        counter = 0
        for item in argv:
            print 'pos: {} value:{}'.format(counter, item)
            counter += 1
        exit(1)


# Main function, we are going to proceed to the finalisation of the dev branch.
if __name__ == "__main__":
    main(sys.argv)
