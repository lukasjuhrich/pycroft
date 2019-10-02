--
-- PostgreSQL database dump
--

-- Dumped from database version 11.1
-- Dumped by pg_dump version 11.1

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: btree_gist; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;


--
-- Name: EXTENSION btree_gist; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION btree_gist IS 'support for indexing common datatypes in GiST';


--
-- Name: ip_port; Type: DOMAIN; Schema: public; Owner: shreyder
--

CREATE DOMAIN public.ip_port AS integer
	CONSTRAINT ip_port_check CHECK (((VALUE >= 1) AND (VALUE <= 65535)));


ALTER DOMAIN public.ip_port OWNER TO shreyder;

--
-- Name: ip_protocol; Type: DOMAIN; Schema: public; Owner: shreyder
--

CREATE DOMAIN public.ip_protocol AS smallint
	CONSTRAINT ip_protocol_check CHECK (((VALUE >= 0) AND (VALUE <= 255)));


ALTER DOMAIN public.ip_protocol OWNER TO shreyder;

--
-- Name: DHCPHostReservation_InsideNetwork_exists(); Type: FUNCTION; Schema: public; Owner: shreyder
--

CREATE FUNCTION public."DHCPHostReservation_InsideNetwork_exists"() RETURNS trigger
    LANGUAGE plpgsql STABLE STRICT LEAKPROOF
    AS $$BEGIN
	IF NOT EXISTS(SELECT FROM "InsideNetwork" WHERE nat_domain = NEW.nat_domain AND ip_network >> NEW.ip) THEN
		RAISE EXCEPTION 'InsideNetwork contains no ip_network for IP % in nat_domain %', NEW.ip, NEW.nat_domain USING ERRCODE = 'integrity_constraint_violation';
	END IF;
	RETURN NEW;
END
$$;


ALTER FUNCTION public."DHCPHostReservation_InsideNetwork_exists"() OWNER TO shreyder;

--
-- Name: Forwarding_Translation_exists(); Type: FUNCTION; Schema: public; Owner: shreyder
--

CREATE FUNCTION public."Forwarding_Translation_exists"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$BEGIN
	IF NOT EXISTS(SELECT FROM "Translation" WHERE nat_domain = NEW.nat_domain AND outside_address = NEW.outside_address AND inside_network >> NEW.inside_address) THEN
		RAISE EXCEPTION 'No corresponding Translation exists for Forwarding: %', NEW USING ERRCODE = 'integrity_constraint_violation';
	END IF;
	RETURN NEW;
END$$;


ALTER FUNCTION public."Forwarding_Translation_exists"() OWNER TO shreyder;

--
-- Name: InsideNetwork_delete(); Type: FUNCTION; Schema: public; Owner: shreyder
--

CREATE FUNCTION public."InsideNetwork_delete"() RETURNS trigger
    LANGUAGE plpgsql STRICT LEAKPROOF
    AS $$BEGIN
	DELETE FROM "DHCPHostReservation" WHERE nat_domain = OLD.nat_domain AND ip << OLD.ip_network;
	DELETE FROM "Translation" WHERE nat_domain = OLD.nat_domain AND inside_network <<= OLD.ip_network;
	RETURN NULL;
END
$$;


ALTER FUNCTION public."InsideNetwork_delete"() OWNER TO shreyder;

--
-- Name: InsideNetwork_truncate(); Type: FUNCTION; Schema: public; Owner: shreyder
--

CREATE FUNCTION public."InsideNetwork_truncate"() RETURNS trigger
    LANGUAGE plpgsql STRICT LEAKPROOF
    AS $$BEGIN
	TRUNCATE "DHCPHostReservation";
	TRUNCATE "Translation";
	RETURN NULL;
END
$$;


ALTER FUNCTION public."InsideNetwork_truncate"() OWNER TO shreyder;

--
-- Name: InsideNetwork_update(); Type: FUNCTION; Schema: public; Owner: shreyder
--

CREATE FUNCTION public."InsideNetwork_update"() RETURNS trigger
    LANGUAGE plpgsql STRICT LEAKPROOF
    AS $$BEGIN
	DELETE FROM "DHCPHostReservation" WHERE nat_domain = OLD.nat_domain AND ip << OLD.ip_network AND NOT ip << NEW.ip_network;
	DELETE FROM "Translation" WHERE nat_domain = OLD.nat_domain AND inside_network <<= OLD.ip_network AND NOT inside_network <<= NEW.ip_network;
	RETURN NULL;
END
$$;


ALTER FUNCTION public."InsideNetwork_update"() OWNER TO shreyder;

--
-- Name: Translation_InsideNetwork_exists(); Type: FUNCTION; Schema: public; Owner: shreyder
--

CREATE FUNCTION public."Translation_InsideNetwork_exists"() RETURNS trigger
    LANGUAGE plpgsql STRICT
    AS $$BEGIN
	IF NOT EXISTS(SELECT FROM "InsideNetwork" WHERE nat_domain = NEW.nat_domain AND ip_network >>= NEW.inside_network) THEN
		--RAISE EXCEPTION 'No corresponding InsideNetwork for Translation: %', NEW USING ERRCODE = 'integrity_constraint_violation';
		RAISE EXCEPTION integrity_constraint_violation USING DETAIL = FORMAT('No corresponding %I for %I: %s', 'InsideNetwork', 'Translation', NEW), TABLE = 'Translation';
	END IF;
	RETURN NEW;
END$$;


ALTER FUNCTION public."Translation_InsideNetwork_exists"() OWNER TO shreyder;

--
-- Name: Translation_delete(); Type: FUNCTION; Schema: public; Owner: shreyder
--

CREATE FUNCTION public."Translation_delete"() RETURNS trigger
    LANGUAGE plpgsql STRICT LEAKPROOF
    AS $$BEGIN
	DELETE FROM "Forwarding" WHERE nat_domain = OLD.nat_domain AND inside_address <<= OLD.inside_network;
	RETURN NULL;
END
$$;


ALTER FUNCTION public."Translation_delete"() OWNER TO shreyder;

--
-- Name: Translation_truncate(); Type: FUNCTION; Schema: public; Owner: shreyder
--

CREATE FUNCTION public."Translation_truncate"() RETURNS trigger
    LANGUAGE plpgsql STRICT LEAKPROOF
    AS $$BEGIN
	TRUNCATE "Forwarding";
	RETURN NULL;
END
$$;


ALTER FUNCTION public."Translation_truncate"() OWNER TO shreyder;

--
-- Name: Translation_update(); Type: FUNCTION; Schema: public; Owner: shreyder
--

CREATE FUNCTION public."Translation_update"() RETURNS trigger
    LANGUAGE plpgsql STRICT LEAKPROOF
    AS $$BEGIN
	DELETE FROM "Forwarding" WHERE nat_domain = OLD.nat_domain AND inside_address <<= OLD.inside_network AND NOT inside_address <<= NEW.inside_network;
	RETURN NULL;
END
$$;


ALTER FUNCTION public."Translation_update"() OWNER TO shreyder;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: DHCPHostReservation; Type: TABLE; Schema: public; Owner: shreyder
--

CREATE TABLE public."DHCPHostReservation" (
    nat_domain integer NOT NULL,
    ip inet NOT NULL,
    mac macaddr NOT NULL
);


ALTER TABLE public."DHCPHostReservation" OWNER TO shreyder;

--
-- Name: Forwarding; Type: TABLE; Schema: public; Owner: shreyder
--

CREATE TABLE public."Forwarding" (
    nat_domain integer NOT NULL,
    outside_address inet NOT NULL,
    protocol public.ip_protocol NOT NULL,
    outside_port public.ip_port,
    inside_address inet NOT NULL,
    inside_port public.ip_port,
    comment text,
    owner integer NOT NULL
);


ALTER TABLE public."Forwarding" OWNER TO shreyder;

--
-- Name: InsideNetwork; Type: TABLE; Schema: public; Owner: shreyder
--

CREATE TABLE public."InsideNetwork" (
    nat_domain integer NOT NULL,
    ip_network inet NOT NULL,
    gateway inet NOT NULL
);


ALTER TABLE public."InsideNetwork" OWNER TO shreyder;

--
-- Name: NATDomain_id_seq; Type: SEQUENCE; Schema: public; Owner: shreyder
--

CREATE SEQUENCE public."NATDomain_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public."NATDomain_id_seq" OWNER TO shreyder;

--
-- Name: NATDomain; Type: TABLE; Schema: public; Owner: shreyder
--

CREATE TABLE public."NATDomain" (
    id integer DEFAULT nextval('public."NATDomain_id_seq"'::regclass) NOT NULL,
    name character varying NOT NULL
);


ALTER TABLE public."NATDomain" OWNER TO shreyder;

--
-- Name: OutsideIPAddress; Type: TABLE; Schema: public; Owner: shreyder
--

CREATE TABLE public."OutsideIPAddress" (
    nat_domain integer NOT NULL,
    ip_address inet NOT NULL,
    owner integer,
    CONSTRAINT "OutsideIPAddress_ip_address_host" CHECK (((family(ip_address) = 4) AND (masklen(ip_address) = 32)))
);


ALTER TABLE public."OutsideIPAddress" OWNER TO shreyder;

--
-- Name: Translation; Type: TABLE; Schema: public; Owner: shreyder
--

CREATE TABLE public."Translation" (
    nat_domain integer NOT NULL,
    outside_address inet NOT NULL,
    inside_network inet NOT NULL,
    owner integer
);


ALTER TABLE public."Translation" OWNER TO shreyder;

--
-- Data for Name: DHCPHostReservation; Type: TABLE DATA; Schema: public; Owner: shreyder
--

COPY public."DHCPHostReservation" (nat_domain, ip, mac) FROM stdin;
1	100.64.1.10	00:11:22:33:44:ff
\.


--
-- Data for Name: Forwarding; Type: TABLE DATA; Schema: public; Owner: shreyder
--

COPY public."Forwarding" (nat_domain, outside_address, protocol, outside_port, inside_address, inside_port, comment, owner) FROM stdin;
\.


--
-- Data for Name: InsideNetwork; Type: TABLE DATA; Schema: public; Owner: shreyder
--

COPY public."InsideNetwork" (nat_domain, ip_network, gateway) FROM stdin;
1	100.64.0.0/24	100.64.0.1
1	100.64.1.0/24	100.64.1.1
\.


--
-- Data for Name: NATDomain; Type: TABLE DATA; Schema: public; Owner: shreyder
--

COPY public."NATDomain" (id, name) FROM stdin;
1	test
\.


--
-- Data for Name: OutsideIPAddress; Type: TABLE DATA; Schema: public; Owner: shreyder
--

COPY public."OutsideIPAddress" (nat_domain, ip_address, owner) FROM stdin;
1	141.30.202.1	\N
1	141.30.202.2	\N
\.


--
-- Data for Name: Translation; Type: TABLE DATA; Schema: public; Owner: shreyder
--

COPY public."Translation" (nat_domain, outside_address, inside_network, owner) FROM stdin;
1	141.30.202.1	100.64.0.0/24	0
\.


--
-- Name: NATDomain_id_seq; Type: SEQUENCE SET; Schema: public; Owner: shreyder
--

SELECT pg_catalog.setval('public."NATDomain_id_seq"', 1, true);


--
-- Name: DHCPHostReservation DHCPHostReservation_ip_check; Type: CHECK CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE public."DHCPHostReservation"
    ADD CONSTRAINT "DHCPHostReservation_ip_check" CHECK (((family(ip) = 4) AND (masklen(ip) = 32))) NOT VALID;


--
-- Name: DHCPHostReservation DHCPHostReservation_pkey; Type: CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."DHCPHostReservation"
    ADD CONSTRAINT "DHCPHostReservation_pkey" PRIMARY KEY (nat_domain, ip);


--
-- Name: Forwarding Forwarding_UniqueOutsidePort_key; Type: CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."Forwarding"
    ADD CONSTRAINT "Forwarding_UniqueOutsidePort_key" UNIQUE (nat_domain, outside_address, protocol, outside_port);


--
-- Name: Forwarding Forwarding_protocol_port_check; Type: CHECK CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE public."Forwarding"
    ADD CONSTRAINT "Forwarding_protocol_port_check" CHECK (
CASE
    WHEN ((outside_port IS NOT NULL) OR (inside_port IS NOT NULL)) THEN ((protocol)::smallint = ANY (ARRAY[6, 17, 33, 132]))
    ELSE NULL::boolean
END) NOT VALID;


--
-- Name: InsideNetwork InsideNetwork_gateway_check; Type: CHECK CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE public."InsideNetwork"
    ADD CONSTRAINT "InsideNetwork_gateway_check" CHECK ((gateway << ip_network)) NOT VALID;


--
-- Name: InsideNetwork InsideNetwork_ip_network_family_check; Type: CHECK CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE public."InsideNetwork"
    ADD CONSTRAINT "InsideNetwork_ip_network_family_check" CHECK ((family(ip_network) = 4)) NOT VALID;


--
-- Name: InsideNetwork InsideNetwork_nat_domain_ip_network_excl; Type: CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."InsideNetwork"
    ADD CONSTRAINT "InsideNetwork_nat_domain_ip_network_excl" EXCLUDE USING gist (nat_domain WITH =, ip_network inet_ops WITH &&);


--
-- Name: InsideNetwork InsideNetwork_pkey; Type: CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."InsideNetwork"
    ADD CONSTRAINT "InsideNetwork_pkey" PRIMARY KEY (nat_domain, ip_network);


--
-- Name: NATDomain NATDomain_pkey; Type: CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."NATDomain"
    ADD CONSTRAINT "NATDomain_pkey" PRIMARY KEY (id);


--
-- Name: OutsideIPAddress OutsideIPAddress_pkey; Type: CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."OutsideIPAddress"
    ADD CONSTRAINT "OutsideIPAddress_pkey" PRIMARY KEY (nat_domain, ip_address);


--
-- Name: Translation Translation_Inside_excl; Type: CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."Translation"
    ADD CONSTRAINT "Translation_Inside_excl" EXCLUDE USING gist (nat_domain WITH =, inside_network inet_ops WITH &&);


--
-- Name: Translation Translation_pkey; Type: CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."Translation"
    ADD CONSTRAINT "Translation_pkey" PRIMARY KEY (nat_domain, outside_address);


--
-- Name: DHCPHostReservation DHCPHostReservation_InsideNetwork_exists; Type: TRIGGER; Schema: public; Owner: shreyder
--

CREATE CONSTRAINT TRIGGER "DHCPHostReservation_InsideNetwork_exists" AFTER INSERT OR UPDATE OF ip ON public."DHCPHostReservation" DEFERRABLE INITIALLY IMMEDIATE FOR EACH ROW EXECUTE PROCEDURE public."DHCPHostReservation_InsideNetwork_exists"();


--
-- Name: InsideNetwork InsideNetwork_delete; Type: TRIGGER; Schema: public; Owner: shreyder
--

CREATE TRIGGER "InsideNetwork_delete" AFTER DELETE ON public."InsideNetwork" FOR EACH ROW EXECUTE PROCEDURE public."InsideNetwork_delete"();


--
-- Name: InsideNetwork InsideNetwork_truncate; Type: TRIGGER; Schema: public; Owner: shreyder
--

CREATE TRIGGER "InsideNetwork_truncate" AFTER TRUNCATE ON public."InsideNetwork" FOR EACH STATEMENT EXECUTE PROCEDURE public."InsideNetwork_truncate"();


--
-- Name: InsideNetwork InsideNetwork_update; Type: TRIGGER; Schema: public; Owner: shreyder
--

CREATE TRIGGER "InsideNetwork_update" AFTER UPDATE OF ip_network ON public."InsideNetwork" FOR EACH ROW EXECUTE PROCEDURE public."InsideNetwork_update"();


--
-- Name: Translation Translation_InsideNetwork_exists; Type: TRIGGER; Schema: public; Owner: shreyder
--

CREATE CONSTRAINT TRIGGER "Translation_InsideNetwork_exists" AFTER INSERT OR UPDATE OF inside_network ON public."Translation" DEFERRABLE INITIALLY IMMEDIATE FOR EACH ROW EXECUTE PROCEDURE public."Translation_InsideNetwork_exists"();


--
-- Name: Translation Translation_truncate; Type: TRIGGER; Schema: public; Owner: shreyder
--

CREATE TRIGGER "Translation_truncate" AFTER TRUNCATE ON public."Translation" FOR EACH STATEMENT EXECUTE PROCEDURE public."Translation_truncate"();


--
-- Name: DHCPHostReservation DHCPHostReservation_NATDomain_fkey; Type: FK CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."DHCPHostReservation"
    ADD CONSTRAINT "DHCPHostReservation_NATDomain_fkey" FOREIGN KEY (nat_domain) REFERENCES public."NATDomain"(id);


--
-- Name: Forwarding Forwarding_DHCPHostReservation_fkey; Type: FK CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."Forwarding"
    ADD CONSTRAINT "Forwarding_DHCPHostReservation_fkey" FOREIGN KEY (inside_address, nat_domain) REFERENCES public."DHCPHostReservation"(ip, nat_domain) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: Forwarding Forwarding_OutsideIPAddress_fkey; Type: FK CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."Forwarding"
    ADD CONSTRAINT "Forwarding_OutsideIPAddress_fkey" FOREIGN KEY (nat_domain, outside_address) REFERENCES public."OutsideIPAddress"(nat_domain, ip_address) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: InsideNetwork InsideNetwork_NATDomain_fkey; Type: FK CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."InsideNetwork"
    ADD CONSTRAINT "InsideNetwork_NATDomain_fkey" FOREIGN KEY (nat_domain) REFERENCES public."NATDomain"(id);


--
-- Name: OutsideIPAddress OutsideIPAddress_NATDomain_fkey; Type: FK CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."OutsideIPAddress"
    ADD CONSTRAINT "OutsideIPAddress_NATDomain_fkey" FOREIGN KEY (nat_domain) REFERENCES public."NATDomain"(id);


--
-- Name: Translation Translation_OutsideIPAddress_fkey; Type: FK CONSTRAINT; Schema: public; Owner: shreyder
--

ALTER TABLE ONLY public."Translation"
    ADD CONSTRAINT "Translation_OutsideIPAddress_fkey" FOREIGN KEY (nat_domain, outside_address) REFERENCES public."OutsideIPAddress"(nat_domain, ip_address);


--
-- PostgreSQL database dump complete
--

