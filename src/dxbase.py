from abc import ABC, abstractmethod
from os.path import exists, isdir
from os import mkdir, remove
from requests import cookies, Request, Session, utils
from requests.cookies import remove_cookie_by_name
from pickle import load, dump, HIGHEST_PROTOCOL
import http.cookiejar
from random import uniform
from time import sleep
from datetime import datetime, timedelta, date



class DataXProc(ABC):
    default_headers = {'Accept': '*/*', 'Accept-Language': 'en-US, en; q=0.7', 'User-Agent': 'curl/7.68.0'}
    r_sleep_min, r_sleep_max = 20, 40

    def __init__(self, cfp, first_url=None, ckeys=None, cfetch_url=None, url_list=None, ck_allow_refresh=False):
        """
        :param cfp: str, import cookies from this file
        :param first_url: str, the very first url from where data can be extracted and analyzed later
        :param ckeys: list, cookie keys that we will need for requests
        :param cfetch_url: str, specify this url from which the cookies will be extracted from
        :param url_list: a list of url pages to be used instead of generating urls
        """
        self.dp = cfp+'_responses'
        self.cfp = cfp+'.ck'
        self.first_url, self.ckeys, self.cfetch_url, self.url_list, self.ck_allow_refresh = first_url, ckeys, cfetch_url, url_list, ck_allow_refresh
        self.responses = []

    def r_status_print_init_cookies(self, txt):
        print(f'Initializing cookies: {txt}')

    def r_status_print_loop(self, i, url):
        print(f' Url {i}: {url}')

    def r_status_print_begin(self):
        sleep(1.2)
        print('----------------------------------------------------------------------')
        print('Beginning..')

    def r_status_print_wait(self, resp_code, f_seconds):
        print(f'\tLast response status code {resp_code}\n\t\tCurrent wait length: {round(f_seconds, 2)}s (avoiding detection)..')

    def r_status_print_finish(self, n):
        print(f'----------------------------------------------------------------------'
              f'\n- Finished! {n} sources have been stored in /{self.dp} directory!')

    def r_loop(self):
        """
        Core method that inits objects, fetches responses and exports cookies to file.

        Uses 'ab_url_nextgen()' to generate new url string.
        """
        try:
            gen_from_list = self.url_list is not None and len(self.url_list) != 0
            sess, req, resp = self.r_init(gen_from_list)
            page_url: 'for consistency' = self.first_url
            self.r_status_print_begin()

            i_counter, len_url_list = 1, len(self.url_list)
            if resp is None: resp = self.r_resp_fetch(sess, req, page_url)

            urlgen, ck_refresh = self.pass_method, self.ck_refresh_pass_method
            urlgen_args, ck_refresh_args = [], [req, resp]

            if gen_from_list:
                lamb_urlgen = lambda l_url_list, l_i_counter: l_url_list[l_i_counter - 1]
                urlgen = lamb_urlgen
                urlgen_args += [self.url_list, i_counter]
            else:
                urlgen = self.ab_url_nextgen
                urlgen_args.append(page_url)

            if self.ck_allow_refresh:
                ck_refresh = self.r_cjar_refresh

            while self.r_resp_ok(resp, i_counter, page_url):
                self.r_resp_export(resp.text)
                if gen_from_list and i_counter == len_url_list:
                    self.r_status_print_finish(i_counter)
                    break
                i_counter += 1
                page_url = urlgen(*urlgen_args)
                req = ck_refresh(*ck_refresh_args)
                resp = self.r_resp_fetch(sess, req, page_url)

            if self.ckeys is not None:
                self.r_cjar_fexport(req.cookies)

        except Exception as ex:
            from sys import exc_info
            from dxexception import dxExceptionReport
            tb = exc_info()[2]
            ex_report = dxExceptionReport(ex, tb)
            print(ex_report.ex_repr)

        else:
            print('\t- no exceptions were raised')

    def r_init(self, gen_from_list):
        """
        Initializes session, header and the default Request objects and fetches the very first relevant response.

        Uses 'ab_r_cookies_webgen()' if not importing cookies from file.

        :return: requests.Session, requests.Request, requests.Response
        """

        if gen_from_list: self.first_url = self.url_list[0]
        c_src_specified = self.cfetch_url is not None
        if not c_src_specified: self.cfetch_url = self.first_url
        if not isdir(self.dp): mkdir(self.dp)
        sess, r_headers = Session(), self.r_headers_gen()
        resp, req = None, self.r_req_prototype(r_headers)

        # cookie generation begins here, using only cfetch_url
        print('----------------------------------------------------------------------')
        if self.ckeys is not None:

            # checking if the cookie file exists and if it does, validate the cookies
            self.r_status_print_init_cookies('looking for cookie file..')
            status_file_str = '\tcookie file found!\n\t'
            cfp_invalid = not exists(self.cfp)
            if not cfp_invalid:
                cjar_expired, cdict = self.r_cjar_expired()
                if cjar_expired:
                    status_file_str += 'cookies expired!'
                    cfp_invalid = True
                else:
                    status_file_str += 'cookies are valid!'
            else:
                status_file_str = 'cookie file not found!'
            print(status_file_str)

            # choosing the correct method to generate new cookies
            cjar = http.cookiejar.CookieJar()
            if not cfp_invalid:     # cfp is invalid if the file doesn't exist or the cookies to be imported have expired
                self.r_status_print_init_cookies('importing cookies from file..')
                self.r_cjar_fimport(cdict, cjar)
            else:
                if not c_src_specified:
                    self.r_status_print_init_cookies('generating online..')
                    resp = self.r_cjar_webgen(sess, req, cjar)
                else:
                    # if a custom cookie url source is specified then implement the 'override_cjar_webgen' method
                    self.r_status_print_init_cookies('using implemented-webgen method..')
                    cjar = self.override_cjar_webgen(sess, req)

            self.cjar_filter(cjar)
            req.cookies = cjar
            self.r_status_print_init_cookies('cookies are ready!')
        else:
            self.r_status_print_init_cookies('cookies are disabled, skipping..')

        return sess, req, resp

    def r_cjar_expired(self):
        self.r_status_print_init_cookies('checking cookie validity..')
        with open(self.cfp, 'rb') as p_ip:
            cdict = load(p_ip)
        today_date = date.today()
        expiration_date = datetime.strptime(cdict['cjar_expiration'], '%Y_%m_%d').date()
        status_expiration_date_str = expiration_date.strftime('%Y-%b-%d')
        print(f'\tcookies valid until: {status_expiration_date_str}')

        if today_date > expiration_date:        # Last saved cookies are expired
            if exists(self.cfp): remove(self.cfp)
            del cdict
            return True, None
        cdict.pop('cjar_expiration')
        return False, cdict

    def r_headers_gen(self):
        """
        Generates specific headers.

        :return: dict, headers to be used in req (and preq)
        """
        from urllib.parse import urlparse

        r_headers = dict(self.default_headers)
        r_headers['Host'] = urlparse(self.cfetch_url).netloc
        return r_headers

    def r_req_prototype(self, r_headers):
        """
        To ensure persistance we create the default requests.Request prototype for requests.Request.prepare().

        :param r_headers: dict, headers that we will use in our requests
        :return: requests.Request
        """
        return Request('GET', headers=r_headers)

    def r_cjar_webgen(self, sess, req, cjar):
        """
        Uses ivar 'cfetch_url' to fetch response and cookies then set req.cookies.

        :param sess: requests.Session
        :param req: requests.Request, our prototype
        :param cjar: http.cookiejar.CookieJar
        :return: requests.Response
        """
        resp = self.r_resp_fetch(sess, req, self.cfetch_url)
        self.cjar_extract_from_resp(req, resp, cjar)
        return resp

    def r_cjar_fimport(self, cdict, cjar):
        """
        Import cookies from file.

        :param cdict: dictionary from file with cookie format
        :param cjar: an empty http.Cookiejar() instance
        """
        utils.cookiejar_from_dict(cdict, cjar)

    def r_cjar_fexport(self, cjar):
        """
        Export cookies to file.

        :param cjar: http.cookiejar.CookieJar
        """
        cdict = utils.dict_from_cookiejar(cjar)
        new_expiration_date_str = self.r_cjar_expirestr_format()
        cdict['cjar_expiration'] = new_expiration_date_str
        with open(self.cfp, 'wb') as p_op:
            dump(cdict, p_op, HIGHEST_PROTOCOL)

    def r_cjar_expirestr_format(self):
        expire_date_calc = date.today() + timedelta(days=1)
        expire_date_str = expire_date_calc.strftime('%Y_%m_%d')
        return expire_date_str

    def r_cjar_refresh(self, req, resp):
        cjar = http.cookiejar.CookieJar()
        self.cjar_extract_from_resp(req, resp, cjar)
        self.cjar_filter(cjar)
        req.cookies = cjar
        return req

    def r_resp_fetch(self, sess, req, page_url):
        """
        Fetches a response. To persist cookies we use the prototype we created in 'r_init'.

        :param sess: requests.Session
        :param req: requests.Request, our prototype
        :param page_url: str, current url
        :return: requests.Response
        """
        req.url = page_url
        preq = req.prepare()
        resp = sess.send(preq)
        return resp

    def r_resp_ok(self, resp, i, page_url):
        """
        Confirms the validity of the response status code.

        :param resp: requests.Response
        :param i:
        :param page_url:
        :return: bool, True if 200, False if not 200
        """
        if resp.status_code != 200 or resp.history:
            self.r_status_print_finish(i-1)
            return False
        self.responses += [resp]
        w_length = uniform(self.r_sleep_min, self.r_sleep_max)
        self.r_status_print_loop(i, page_url)
        self.r_status_print_wait(resp.status_code, w_length)
        self.r_sleep(w_length)
        return True

    def r_sleep(self, w_length):
        """
        Sleep for a random amount of time to avoid server overload. Min of 20 seconds is generally okay, min. of 30
        seconds and higher safest. Floats are used to avoid robotic activity suspicion. Default interval in cvar
        'r_sleep_min, r_sleep_max'.
        """
        sleep(w_length)

    def cjar_extract_from_resp(self, req, resp, cjar):
        """
        Extract cookies from requests.Response object.

        :param req: requests.Request, our prototype
        :param resp: requests.Response
        :param cjar: http.cookiejar.CookieJar
        """
        cookies.extract_cookies_to_jar(cjar, req, resp.raw)

    def cjar_filter(self, cjar):
        """
        Filter cookie keys so we use only those that we need specified in ivar 'ckeys'.

        :param cjar: http.cookiejar.CookieJar
        """
        for cjar_key in cjar:
            if cjar_key.name not in self.ckeys: remove_cookie_by_name(cjar, cjar_key.name)

    def r_resp_export(self, text):
        dt_now_str = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        resp_fn_loc = f'{self.dp}/response_{dt_now_str}.txt'
        with open(resp_fn_loc, 'w') as f: f.write(text)

    def pass_method(self, *args):
        """
        To balance the cost of readability and compile time, this method was created for the r_loop method to be used
        for specific boolean events in a loop. Therefore we simply just call this method and exit it. This way,
        instead of using several decision making statements that would cost more in terms of compile time (and even
        readability), we use this.

        :param args:
        :return:
        """
        pass

    def ck_refresh_pass_method(self, *args):
        """
        Designed for the same reasons as 'pass_method', but more specific for the local ck_refresh method.
        It is only used in case ivar ck_allow_refresh is True.

        :param args: we don't use any of the arguments, similar to the pass method.
        :return: However, we need to return with the Request object, because that is one of the default arguments.
        """
        return args[0]

    # Optional semi-abstract method
    def override_cjar_webgen(self, sess, req) -> http.cookiejar.CookieJar:
        """
        Override this method and implement a function that returns a CookieJar in case you need a special method to
        generate one. Use sess and req if using requests.

        CAUTION: Ensure that the data types (such as returns, args, etc..) are compatible

        :param sess: requests.Session
        :param req: requests.Request
        :return: http.cookiejar.CookieJar
        """
        pass

    @abstractmethod
    def ab_url_nextgen(self, current_url):
        """
        :return: str, next page's url
        """
        pass
