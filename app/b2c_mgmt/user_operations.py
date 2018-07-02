from azure.graphrbac import GraphRbacManagementClient
from azure.common.credentials import ServicePrincipalCredentials
from azure.graphrbac.models import PasswordProfile, SignInName, UserUpdateParameters
from app.b2c_mgmt.user.hisc_user_create_parameters import HISCUserCreateParameters
import string, json

def b2c_user(email, config):
    filterTemplate=string.Template("otherMails/any(c:c eq '$email')")
    filter = filterTemplate.substitute(email=email)
    user = next(_client(config).users.list(filter=filter), None)
    return json.dumps(_convert_user(user), indent=4, sort_keys=True)

def b2c_users(config, franchises):
    client = _client(config)
    group_names = (franchises + ['CAREGiver'])
    group_ids = _group_ids(config, client, group_names)
    user_lists = [[_convert_user(user) for user in client.groups.get_group_members(group)] for group in group_ids]
    return _unique_users(user_lists)

def _unique_users(list_of_user_lists):
    # This is absolutely convoluted.   We have to grab CAREGivers who are in Franchise 100 so it's an
    # intersection of the two groups.  If only we could filter users by groups this would be much easier.
    list_of_id_lists = [[user['objectId'] for user in user_list] for user_list in list_of_user_lists]
    unique_user_ids = set(list_of_id_lists[0]).intersection(*list_of_id_lists)
    return [user for user in list_of_user_lists[0] if (user['objectId'] in unique_user_ids)]

def create_user(config, first_name, last_name, email, franchise_number):
    client = _client(config)
    user = client.users.create(_user_create_parameters(first_name, last_name, email, config))
    user_url = _user_url(config, user.object_id)
    [client.groups.add_member(group_id, user_url) for group_id in _group_ids(config, client, [franchise_number, 'CAREGiver'])]
    return user.serialize()

def _convert_user(user):
    if user:
        user.enable_additional_properties_sending()
        return user.serialize()
    return None

def _client(config):
	return GraphRbacManagementClient(_credentials(config), config['graph_tenant_id'])

def _credentials(config):
	return ServicePrincipalCredentials(
        client_id=config['graph_client_id'],
        secret=config['graph_client_secret'],
        tenant=config['graph_tenant_id'],
        resource=config['ad_graph_url'])

def _group_ids(config, client, groups):
    # really we need logic here to create franchises that don't existself.
    return [group.object_id for group in client.groups.list(filter=_group_filter(groups))]

def _group_filter(groups):
    template = "displayName eq '{}'"
    filters = [template.format(group) for group in groups]
    return ' or '.join(filters)

def _user_url(config, user_id):
    template = 'https://graph.windows.net/{}/users/{}'
    return template.format(config['graph_tenant_id'], user_id)

def _user_create_parameters(first_name, last_name, email, config):
	return HISCUserCreateParameters(
		account_enabled=True,
		sign_in_names=[_sign_in_name(email)],
		creation_type='LocalAccount',
		display_name='{}.{}'.format(first_name, last_name),
		mail_nickname=_mail_nickname(email),
		password_profile=_password_profile(config),
		user_principal_name=_principle_name(email, config),
		given_name=first_name,
		surname=last_name,
		other_mails=[email],
		usage_location='US'
    )

def _password_profile(config):
	return PasswordProfile(password=config['default_password'], force_change_password_next_login=True)

def _principle_name(email, config):
	return config['principle_template'].format(_mail_nickname(email))

def _mail_nickname(email):
	return '{}#EXT#'.format(_format_email(email))

def _format_email(email):
	return email.replace('@', '_')

def _sign_in_name(email):
	return SignInName(type='emailAddress', value=email)
