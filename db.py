from utils import base36_encode


def insert_url(redis, url):
    short_id = redis.get("reverse-url:" + url)
    if short_id is not None:
        return short_id
    short_id = redis.incr("last-url-id")
    redis.set("url-target:" + str(short_id), url)
    redis.set("reverse-url:" + url, str(short_id))
    return short_id


def get_url(redis, short_id):
    return redis.get("url-target:" + short_id)


def increment_url(redis, short_id):
    redis.incr("click-count:" + short_id)


def get_count(redis, short_id):
    return int(redis.get("click-count:" + short_id) or 0)


def get_list_urls(redis):
    url_num = int(redis.get("last-url-id"))
    list_urls = list()
    for id in range(1, url_num+1):
        d_url = dict()
        short_id = str(id)
        d_url['id'] = short_id
        d_url['url'] = get_url(redis, short_id)
        d_url['count'] = get_count(redis, short_id)
        list_urls.append(d_url)
    return list_urls
