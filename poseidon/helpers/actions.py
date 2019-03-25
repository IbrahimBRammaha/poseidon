# -*- coding: utf-8 -*-
"""
Created on 9 December 2018
@author: Charlie Lewis
"""
from poseidon.helpers.collector import Collector


class Actions(object):

    def __init__(self, endpoint, sdnc):
        self.endpoint = endpoint
        self.sdnc = sdnc

    def shutdown_endpoint(self):
        ''' tell the controller to shutdown an endpoint '''
        self.sdnc.shutdown_endpoint()
        return

    def mirror_endpoint(self):
        '''
        tell vent to start a collector and the controller to begin
        mirroring traffic
        '''
        status = False
        if self.sdnc.mirror_mac(self.endpoint.endpoint_data['mac'], self.endpoint.endpoint_data['segment'], self.endpoint.endpoint_data['port']):
            status = Collector(self.endpoint).start_vent_collector()
        return status

    def unmirror_endpoint(self):
        ''' tell the controller to unmirror traffic '''
        status = False
        if self.sdnc.unmirror_mac(self.endpoint.endpoint_data['mac'], self.endpoint.endpoint_data['segment'], self.endpoint.endpoint_data['port']):
            status = Collector(self.endpoint).stop_vent_collector()
        return status
